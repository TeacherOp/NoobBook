"""
Database Processor - Handles DATABASE source processing (Postgres/MySQL).

Educational Note: A database source is processed by capturing a schema snapshot
(tables + basic metadata). This snapshot is stored as a processed text file in
Supabase Storage, then embedded + summarized like other sources.

This enables:
- Quick schema understanding in the Sources UI (processed content viewer)
- RAG over schema metadata (search_sources)
- A foundation for a database query agent (tool-based SQL querying)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg2

logger = logging.getLogger(__name__)
from psycopg2.extras import RealDictCursor
import pymysql

from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service
from app.services.data_services.database_connection_service import database_connection_service
from app.services.integrations.supabase import storage_service


def _load_raw_metadata(raw_file_path: Path) -> Dict[str, Any]:
    """Load `.database` raw metadata JSON."""
    try:
        with open(raw_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _connect_postgres(connection_uri: str):
    """Create a PostgreSQL connection."""
    return psycopg2.connect(connection_uri, connect_timeout=5)


def _connect_mysql(connection_uri: str):
    """Create a MySQL connection."""
    parsed = urlparse(connection_uri)
    if not parsed.hostname:
        raise ValueError("Invalid MySQL connection URI")

    return pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database=(parsed.path or "").lstrip("/") or None,
        connect_timeout=5,
        read_timeout=30,
        write_timeout=30,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _fetch_table_list_postgres(conn) -> List[Dict[str, Any]]:
    """Fetch table list + descriptions (public schema)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
        SELECT
            t.table_name,
            t.table_type,
            obj_description(c.oid, 'pg_class') as table_description,
            c.reltuples::bigint as estimated_row_count
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name
        WHERE t.table_schema = 'public'
          AND t.table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY t.table_name
        """
        cur.execute(query)
        rows = cur.fetchall() or []
        tables: List[Dict[str, Any]] = []
        for r in rows:
            tables.append(
                {
                    "name": r.get("table_name"),
                    "type": r.get("table_type"),
                    "description": (r.get("table_description") or "").strip(),
                    "row_count_estimate": int(r.get("estimated_row_count") or 0),
                }
            )
        return tables
    finally:
        cur.close()


def _fetch_table_list_mysql(conn) -> List[Dict[str, Any]]:
    """Fetch table list + comments from information_schema."""
    with conn.cursor() as cur:
        query = """
        SELECT
            TABLE_NAME as table_name,
            TABLE_TYPE as table_type,
            TABLE_COMMENT as table_description,
            TABLE_ROWS as row_count
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
        ORDER BY TABLE_NAME
        """
        cur.execute(query)
        rows = cur.fetchall() or []
        tables: List[Dict[str, Any]] = []
        for r in rows:
            tables.append(
                {
                    "name": r.get("table_name"),
                    "type": r.get("table_type"),
                    "description": (r.get("table_description") or "").strip(),
                    "row_count_estimate": int(r.get("row_count") or 0),
                }
            )
        return tables


def _build_processed_text(
    source_name: str,
    db_type: str,
    database_name: str,
    captured_at: str,
    tables: List[Dict[str, Any]],
) -> str:
    """Build processed text snapshot (stored in Supabase processed-files bucket)."""
    header_lines = [
        f"# Extracted from DATABASE: {source_name}",
        "# Type: DATABASE",
        f"# Database Type: {db_type}",
        f"# Database Name: {database_name or '(unknown)'}",
        f"# Captured at: {captured_at}",
        "# ---",
        "",
    ]

    lines = [
        "## Database Schema Snapshot",
        "",
        f"Total tables/views: {len(tables)}",
        "",
        "### Tables",
        "",
    ]

    # Keep this readable: sorted by name (already sorted by query).
    for t in tables:
        name = t.get("name") or ""
        table_type = t.get("type") or ""
        desc = t.get("description") or ""
        row_est = t.get("row_count_estimate", 0)

        lines.append(f"- **{name}** ({table_type})")
        if row_est:
            lines.append(f"  - Rows (estimate): {row_est}")
        if desc:
            lines.append(f"  - Description: {desc}")

    lines.append("")
    lines.append(
        "Tip: Use the database query agent in chat to ask questions that require live data."
    )
    lines.append("")

    return "\n".join(header_lines + lines)


def process_database(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service,
) -> Dict[str, Any]:
    """
    Process a DATABASE source:
    1) Load raw metadata (.database)
    2) Fetch table list from the external DB
    3) Save schema snapshot as processed text in Supabase Storage
    4) Embed + summarize like other sources
    5) Mark source ready
    """
    captured_at = datetime.now().isoformat()

    embedding_info = source.get("embedding_info", {}) or {}
    raw_meta = _load_raw_metadata(raw_file_path)

    connection_id = embedding_info.get("connection_id") or raw_meta.get("connection_id")
    if not connection_id:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Database source missing connection_id"},
        )
        return {"success": False, "error": "Missing connection_id"}

    # Load connection secret from account-level table.
    # Uses _server_internal=True to skip user-level access control —
    # the source was already authorized at upload time.
    logger.info(
        "DB processor: resolving connection_id=%s (source_id=%s)",
        connection_id, source_id,
    )
    connection = database_connection_service.get_connection(
        connection_id=connection_id,
        include_secret=True,
        _server_internal=True,
    )
    if not connection:
        error_msg = (
            f"Database connection not found (connection_id={connection_id}). "
            f"Verify the connection exists in Settings → Databases."
        )
        logger.error("DB processor: %s", error_msg)
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": error_msg},
        )
        return {"success": False, "error": error_msg}

    db_type = (connection.get("db_type") or "postgresql").lower()
    connection_uri = connection.get("connection_uri") or ""
    database_name = embedding_info.get("database_name") or raw_meta.get("database_name") or ""

    # Fetch schema snapshot
    tables: List[Dict[str, Any]] = []
    try:
        if db_type == "mysql":
            conn = _connect_mysql(connection_uri)
            try:
                tables = _fetch_table_list_mysql(conn)
            finally:
                conn.close()
        else:
            conn = _connect_postgres(connection_uri)
            try:
                tables = _fetch_table_list_postgres(conn)
            finally:
                conn.close()
    except Exception as e:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": f"Failed to fetch schema: {str(e)}"},
        )
        return {"success": False, "error": str(e)}

    processed_text = _build_processed_text(
        source_name=source.get("name", "Database"),
        db_type=db_type,
        database_name=database_name,
        captured_at=captured_at,
        tables=tables,
    )

    # Upload processed schema snapshot
    processed_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=processed_text,
    )
    if not processed_path:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Failed to upload processed schema snapshot"},
        )
        return {"success": False, "error": "Failed to upload processed file"}

    processing_info = {
        "processor": "database_schema_snapshot",
        "captured_at": captured_at,
        "db_type": db_type,
        "database_name": database_name,
        "table_count": len(tables),
    }

    # Skip embedding — database sources are queried via the dedicated
    # analyze_database_agent tool, not through RAG search_sources.
    merged_embedding_info = {
        **embedding_info,
        "connection_id": connection_id,
        "db_type": db_type,
        "database_name": database_name,
        "is_embedded": False,
        "file_extension": ".database",
    }

    # Summarize schema snapshot (AI)
    summary_info: Dict[str, Any] = {}
    try:
        summary_source_metadata = {
            "name": source.get("name", "Database"),
            "category": "database",
            "file_extension": ".database",
            "embedding_info": merged_embedding_info,
            "processing_info": {**processing_info, "total_pages": max(1, len(tables))},
        }
        summary_info = summary_service.generate_summary(project_id, source_id, summary_source_metadata) or {}
    except Exception as e:
        logger.exception("Summary generation failed for source %s", source_id)
        summary_info = {}

    source_service.update_source(
        project_id,
        source_id,
        status="ready",
        processing_info=processing_info,
        embedding_info=merged_embedding_info,
        summary_info=summary_info if summary_info else None,
    )

    return {"success": True, "status": "ready"}
