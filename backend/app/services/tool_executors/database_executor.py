"""
Database Executor - Executes database agent tools (schema_fetcher, query_runner).

Educational Note: This executor powers the database analyzer agent by:
1) Fetching schema metadata (tables, columns, keys)
2) Running safe, read-only SQL queries (SELECT/WITH only)
3) Returning structured results for the agent to reason over

Security:
- Only SELECT/WITH queries are permitted.
- We reject known write/DDL keywords and multi-statement queries.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor
import pymysql

from app.services.data_services.database_connection_service import database_connection_service
from app.services.source_services import source_service

logger = logging.getLogger(__name__)


MAX_QUERY_ROWS = 100

# Only allow simple identifiers to prevent injection via identifier fields.
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?$")
_SAFE_IDENTIFIER_PART_RE = re.compile(r"^[A-Za-z0-9_]+$")

# Guardrail for read-only queries.
_UNSAFE_SQL_KEYWORDS_RE = re.compile(
    r"(^|\s)(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|MERGE|CALL|EXECUTE|COPY)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _ResolvedConnection:
    connection_id: str
    db_type: str  # "postgresql" | "mysql"
    connection_uri: str


def _serialize_value(value: Any) -> Any:
    """Convert values to JSON-serializable types for tool results."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _serialize_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    """Serialize query results (list of dict-like rows)."""
    serialized: List[Dict[str, Any]] = []
    for row in rows:
        # psycopg2 RealDictCursor returns RealDictRow; pymysql DictCursor returns dict.
        row_dict = dict(row)
        serialized.append({k: _serialize_value(v) for k, v in row_dict.items()})
    return serialized


def _quote_identifier(db_type: str, identifier: str) -> str:
    """Quote a SQL identifier safely after validation."""
    if not identifier or not _SAFE_IDENTIFIER_RE.match(identifier):
        raise ValueError("Invalid identifier")

    parts = identifier.split(".")
    if db_type == "mysql":
        return ".".join([f"`{p}`" for p in parts])
    return ".".join([f"\"{p}\"" for p in parts])


def _validate_readonly_query(query: str) -> Tuple[bool, str]:
    """Validate the query is a single, read-only SELECT/WITH query."""
    if not query or not query.strip():
        return False, "query is required"

    normalized = query.strip()

    # Disallow multiple statements.
    if ";" in normalized.rstrip(";"):
        return False, "Multiple SQL statements are not allowed"

    normalized = normalized.rstrip(";").strip()
    first_token = (normalized.split(None, 1)[0] or "").upper()
    if first_token not in {"SELECT", "WITH"}:
        return False, "Only SELECT/WITH queries are allowed"

    if _UNSAFE_SQL_KEYWORDS_RE.search(normalized):
        return False, "Query contains unsafe operation. Only read-only queries are allowed."

    return True, ""


class DatabaseExecutor:
    """
    Executor for database agent tools.

    Educational Note: The database analyzer agent is scoped to a single DATABASE source_id.
    Tool inputs do not include credentials or connection info; we resolve that server-side.
    """

    def __init__(self) -> None:
        self._conn_cache: Dict[str, Any] = {}
        self._conn_type_cache: Dict[str, str] = {}

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def close_connections(self) -> None:
        """Close any cached DB connections."""
        for conn in self._conn_cache.values():
            try:
                conn.close()
            except Exception:
                pass
        self._conn_cache.clear()
        self._conn_type_cache.clear()

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        project_id: str,
        source_id: str,
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a database agent tool.

        Returns:
            Tuple(result_dict, is_termination)
        """
        if tool_name == "schema_fetcher":
            return self._schema_fetcher(tool_input, project_id, source_id), False

        if tool_name == "query_runner":
            return self._query_runner(tool_input, project_id, source_id), False

        if tool_name == "return_database_result":
            return tool_input, True

        return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    # ---------------------------------------------------------------------
    # Connection resolution
    # ---------------------------------------------------------------------

    def _resolve_connection(self, project_id: str, source_id: str) -> _ResolvedConnection:
        # Step 1: Load the source record from Supabase
        source = source_service.get_source(project_id, source_id)
        if not source:
            logger.error(
                "DB resolve: source not found — project_id=%s, source_id=%s",
                project_id, source_id,
            )
            raise ValueError(
                f"Source not found (project_id={project_id}, source_id={source_id})"
            )

        # Step 2: Verify this is a DATABASE source
        embedding_info = source.get("embedding_info", {}) or {}
        file_extension = (embedding_info.get("file_extension") or "").lower()
        if file_extension != ".database":
            raise ValueError(
                f"Source is not a DATABASE source (file_extension={file_extension})"
            )

        # Step 3: Extract connection_id from embedding_info
        connection_id = embedding_info.get("connection_id")
        if not connection_id:
            logger.error(
                "DB resolve: connection_id missing in embedding_info — "
                "source_id=%s, embedding_info_keys=%s",
                source_id, list(embedding_info.keys()),
            )
            raise ValueError(
                f"Database source missing connection_id in embedding_info "
                f"(source_id={source_id})"
            )

        # Step 4: Load the connection record (with credentials)
        # Uses _server_internal=True to skip user-level access control.
        # The source was already authorized at upload time.
        connection = database_connection_service.get_connection(
            connection_id=connection_id,
            include_secret=True,
            _server_internal=True,
        )
        if not connection:
            logger.error(
                "DB resolve: connection not found — "
                "connection_id=%s, source_id=%s. "
                "The connection may have been deleted.",
                connection_id, source_id,
            )
            raise ValueError(
                f"Database connection not found (connection_id={connection_id}). "
                f"Check that the connection still exists in Settings → Databases."
            )

        db_type = (connection.get("db_type") or "postgresql").lower()
        connection_uri = connection.get("connection_uri") or ""

        if db_type not in {"postgresql", "mysql"}:
            raise ValueError(f"Unsupported db_type: {db_type}")

        if not connection_uri:
            raise ValueError(
                f"Connection has empty connection_uri (connection_id={connection_id})"
            )

        return _ResolvedConnection(
            connection_id=connection_id,
            db_type=db_type,
            connection_uri=connection_uri,
        )

    def _get_connection(self, project_id: str, source_id: str) -> Tuple[Any, _ResolvedConnection]:
        resolved = self._resolve_connection(project_id, source_id)

        cached = self._conn_cache.get(resolved.connection_id)
        cached_type = self._conn_type_cache.get(resolved.connection_id)
        if cached is not None and cached_type == resolved.db_type:
            # Best-effort liveness check
            try:
                if resolved.db_type == "mysql":
                    cached.ping(reconnect=False)
                else:
                    with cached.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                return cached, resolved
            except Exception:
                try:
                    cached.close()
                except Exception:
                    pass
                self._conn_cache.pop(resolved.connection_id, None)
                self._conn_type_cache.pop(resolved.connection_id, None)

        conn = self._connect(resolved.db_type, resolved.connection_uri)
        self._conn_cache[resolved.connection_id] = conn
        self._conn_type_cache[resolved.connection_id] = resolved.db_type
        return conn, resolved

    def validate_connection(self, project_id: str, source_id: str) -> _ResolvedConnection:
        """Pre-flight: verify the DB connection is resolvable. Caches for reuse."""
        _, resolved = self._get_connection(project_id, source_id)
        return resolved

    @staticmethod
    def _connect(db_type: str, connection_uri: str) -> Any:
        # Parse the URI to extract host for logging (never log passwords)
        parsed_for_log = urlparse(connection_uri)
        host_for_log = f"{parsed_for_log.hostname}:{parsed_for_log.port or 'default'}"

        try:
            if db_type == "mysql":
                parsed = urlparse(connection_uri)
                if not parsed.hostname:
                    raise ValueError("Invalid MySQL connection URI — no hostname")

                return pymysql.connect(
                    host=parsed.hostname,
                    port=parsed.port or 3306,
                    user=parsed.username,
                    password=parsed.password,
                    database=(parsed.path or "").lstrip("/") or None,
                    connect_timeout=10,
                    read_timeout=30,
                    write_timeout=30,
                    autocommit=True,
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                )

            conn = psycopg2.connect(connection_uri, connect_timeout=10)
            # Try to enforce read-only where possible.
            try:
                conn.set_session(readonly=True, autocommit=True)
            except Exception:
                conn.autocommit = True
            return conn

        except Exception as e:
            logger.error(
                "Failed to connect to %s database at %s: %s",
                db_type, host_for_log, e,
            )
            raise ValueError(
                f"Cannot connect to {db_type} database at {host_for_log}: {e}"
            ) from e

    # ---------------------------------------------------------------------
    # Tools
    # ---------------------------------------------------------------------

    def _schema_fetcher(self, tool_input: Dict[str, Any], project_id: str, source_id: str) -> Dict[str, Any]:
        table_names = tool_input.get("table_names") or []
        if not isinstance(table_names, list):
            table_names = []

        try:
            conn, resolved = self._get_connection(project_id, source_id)

            if resolved.db_type == "mysql":
                if not table_names:
                    return self._mysql_table_overview(conn)
                return self._mysql_table_details(conn, table_names)

            # PostgreSQL
            if not table_names:
                return self._postgres_table_overview(conn)
            return self._postgres_table_details(conn, table_names)

        except Exception as e:
            logger.error("schema_fetcher failed (source_id=%s): %s", source_id, e)
            return {"success": False, "error": str(e)}

    def _query_runner(self, tool_input: Dict[str, Any], project_id: str, source_id: str) -> Dict[str, Any]:
        query = tool_input.get("query", "")
        ok, err = _validate_readonly_query(query)
        if not ok:
            return {"success": False, "error": err}

        normalized = query.strip().rstrip(";").strip()

        try:
            conn, resolved = self._get_connection(project_id, source_id)

            start = time.time()

            # Best-effort per-session query timeout.
            try:
                if resolved.db_type == "mysql":
                    with conn.cursor() as cur:
                        cur.execute("SET SESSION MAX_EXECUTION_TIME=10000")
                else:
                    with conn.cursor() as cur:
                        cur.execute("SET statement_timeout = 10000")
            except Exception:
                pass

            if resolved.db_type == "mysql":
                with conn.cursor() as cur:
                    cur.execute(normalized)
                    rows = cur.fetchmany(MAX_QUERY_ROWS + 1)
                    truncated = len(rows) > MAX_QUERY_ROWS
                    rows = rows[:MAX_QUERY_ROWS]
                    col_names = [d[0] for d in (cur.description or [])]
            else:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(normalized)
                    rows = cur.fetchmany(MAX_QUERY_ROWS + 1)
                    truncated = len(rows) > MAX_QUERY_ROWS
                    rows = rows[:MAX_QUERY_ROWS]
                    col_names = [d[0] for d in (cur.description or [])]

            elapsed_ms = (time.time() - start) * 1000

            return {
                "success": True,
                "database_type": resolved.db_type,
                "query": normalized,
                "row_count": len(rows),
                "results": _serialize_rows(rows),
                "column_names": col_names,
                "execution_time_ms": round(elapsed_ms, 2),
                "truncated": truncated,
                "limit": MAX_QUERY_ROWS,
            }

        except Exception as e:
            logger.error("query_runner failed (source_id=%s): %s", source_id, e)
            return {"success": False, "error": f"Query execution failed: {str(e)}", "query": normalized}

    # ---------------------------------------------------------------------
    # Schema helpers (PostgreSQL)
    # ---------------------------------------------------------------------

    @staticmethod
    def _postgres_table_overview(conn) -> Dict[str, Any]:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
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
            )
            rows = cur.fetchall() or []

        tables = [
            {
                "name": r.get("table_name"),
                "type": r.get("table_type"),
                "description": (r.get("table_description") or "").strip(),
                "row_count_estimate": int(r.get("estimated_row_count") or 0),
            }
            for r in rows
        ]

        return {
            "success": True,
            "database_type": "postgresql",
            "table_count": len(tables),
            "tables": tables,
        }

    @staticmethod
    def _postgres_table_details(conn, table_names: List[str]) -> Dict[str, Any]:
        detailed_tables: List[Dict[str, Any]] = []

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for raw_name in table_names:
                try:
                    safe_name = raw_name.strip()
                    if not _SAFE_IDENTIFIER_RE.match(safe_name):
                        detailed_tables.append(
                            {"name": raw_name, "success": False, "error": "Invalid table name"}
                        )
                        continue
                    schema_name = "public"
                    table_name = safe_name
                    if "." in safe_name:
                        schema_name, table_name = safe_name.split(".", 1)
                        if not _SAFE_IDENTIFIER_PART_RE.match(schema_name) or not _SAFE_IDENTIFIER_PART_RE.match(
                            table_name
                        ):
                            detailed_tables.append(
                                {"name": raw_name, "success": False, "error": "Invalid table name"}
                            )
                            continue

                    # Basic table info
                    cur.execute(
                        """
                        SELECT
                            t.table_name,
                            t.table_type,
                            obj_description(c.oid, 'pg_class') as table_description,
                            c.reltuples::bigint as estimated_row_count
                        FROM information_schema.tables t
                        LEFT JOIN pg_class c ON c.relname = t.table_name
                        WHERE t.table_schema = %s AND t.table_name = %s
                        """,
                        (schema_name, table_name),
                    )
                    table_row = cur.fetchone() or {}

                    # Columns
                    cur.execute(
                        """
                        SELECT
                            column_name,
                            data_type,
                            is_nullable,
                            column_default,
                            character_maximum_length,
                            numeric_precision,
                            numeric_scale,
                            ordinal_position
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                        """,
                        (schema_name, table_name),
                    )
                    cols = cur.fetchall() or []

                    # Primary keys
                    cur.execute(
                        """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.table_schema = %s
                          AND tc.table_name = %s
                          AND tc.constraint_type = 'PRIMARY KEY'
                        ORDER BY kcu.ordinal_position
                        """,
                        (schema_name, table_name),
                    )
                    pk_cols = {r.get("column_name") for r in (cur.fetchall() or [])}

                    # Foreign keys
                    cur.execute(
                        """
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS foreign_table,
                            ccu.column_name AS foreign_column
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage ccu
                          ON ccu.constraint_name = tc.constraint_name
                         AND ccu.table_schema = tc.table_schema
                        WHERE tc.table_schema = %s
                          AND tc.table_name = %s
                          AND tc.constraint_type = 'FOREIGN KEY'
                        """,
                        (schema_name, table_name),
                    )
                    fk_rows = cur.fetchall() or []

                    fk_map: Dict[str, Dict[str, str]] = {}
                    for r in fk_rows:
                        col = r.get("column_name")
                        if not col:
                            continue
                        fk_map[col] = {
                            "foreign_table": r.get("foreign_table"),
                            "foreign_column": r.get("foreign_column"),
                        }

                    columns: List[Dict[str, Any]] = []
                    for c in cols:
                        cname = c.get("column_name")
                        col_out = {
                            "column_name": cname,
                            "data_type": c.get("data_type"),
                            "is_nullable": c.get("is_nullable") == "YES",
                            "default": c.get("column_default"),
                            "ordinal_position": c.get("ordinal_position"),
                        }
                        if cname in pk_cols:
                            col_out["is_primary_key"] = True
                        if cname in fk_map:
                            col_out.update(fk_map[cname])
                        if c.get("character_maximum_length") is not None:
                            col_out["max_length"] = c.get("character_maximum_length")
                        if c.get("numeric_precision") is not None:
                            col_out["numeric_precision"] = c.get("numeric_precision")
                        if c.get("numeric_scale") is not None:
                            col_out["numeric_scale"] = c.get("numeric_scale")
                        columns.append(col_out)

                    # Sample row (best-effort)
                    sample_data: List[Dict[str, Any]] = []
                    try:
                        quoted = _quote_identifier("postgresql", f"{schema_name}.{table_name}")
                        cur.execute(f"SELECT * FROM {quoted} LIMIT 1")
                        sample_rows = cur.fetchall() or []
                        sample_data = _serialize_rows(sample_rows)
                    except Exception:
                        sample_data = []

                    detailed_tables.append(
                        {
                            "success": True,
                            "name": f"{schema_name}.{table_name}" if schema_name else table_name,
                            "type": table_row.get("table_type"),
                            "description": (table_row.get("table_description") or "").strip(),
                            "row_count_estimate": int(table_row.get("estimated_row_count") or 0),
                            "columns": columns,
                            "sample_data": sample_data,
                        }
                    )

                except Exception as e:
                    detailed_tables.append({"name": raw_name, "success": False, "error": str(e)})

        return {
            "success": True,
            "database_type": "postgresql",
            "table_count": len(detailed_tables),
            "tables": detailed_tables,
        }

    # ---------------------------------------------------------------------
    # Schema helpers (MySQL)
    # ---------------------------------------------------------------------

    @staticmethod
    def _mysql_table_overview(conn) -> Dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
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
            )
            rows = cur.fetchall() or []

        tables = [
            {
                "name": r.get("table_name"),
                "type": r.get("table_type"),
                "description": (r.get("table_description") or "").strip(),
                "row_count_estimate": int(r.get("row_count") or 0),
            }
            for r in rows
        ]

        return {
            "success": True,
            "database_type": "mysql",
            "table_count": len(tables),
            "tables": tables,
        }

    @staticmethod
    def _mysql_table_details(conn, table_names: List[str]) -> Dict[str, Any]:
        detailed_tables: List[Dict[str, Any]] = []

        with conn.cursor() as cur:
            for raw_name in table_names:
                try:
                    safe_name = raw_name.strip()
                    if not _SAFE_IDENTIFIER_RE.match(safe_name):
                        detailed_tables.append(
                            {"name": raw_name, "success": False, "error": "Invalid table name"}
                        )
                        continue
                    table_name = safe_name.split(".", 1)[-1]
                    if not _SAFE_IDENTIFIER_PART_RE.match(table_name):
                        detailed_tables.append(
                            {"name": raw_name, "success": False, "error": "Invalid table name"}
                        )
                        continue

                    # Table info
                    cur.execute(
                        """
                        SELECT
                            TABLE_NAME as table_name,
                            TABLE_TYPE as table_type,
                            TABLE_COMMENT as table_description,
                            TABLE_ROWS as row_count
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                        """,
                        (table_name,),
                    )
                    table_row = cur.fetchone() or {}

                    # Columns
                    cur.execute(
                        """
                        SELECT
                            COLUMN_NAME as column_name,
                            DATA_TYPE as data_type,
                            COLUMN_TYPE as column_type,
                            IS_NULLABLE as is_nullable,
                            COLUMN_DEFAULT as column_default,
                            ORDINAL_POSITION as ordinal_position
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                        """,
                        (table_name,),
                    )
                    cols = cur.fetchall() or []

                    # Primary keys
                    cur.execute(
                        """
                        SELECT COLUMN_NAME as column_name
                        FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                          AND CONSTRAINT_NAME = 'PRIMARY'
                        ORDER BY ORDINAL_POSITION
                        """,
                        (table_name,),
                    )
                    pk_cols = {r.get("column_name") for r in (cur.fetchall() or [])}

                    # Foreign keys
                    cur.execute(
                        """
                        SELECT
                            COLUMN_NAME as column_name,
                            REFERENCED_TABLE_NAME as foreign_table,
                            REFERENCED_COLUMN_NAME as foreign_column
                        FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                          AND REFERENCED_TABLE_NAME IS NOT NULL
                        """,
                        (table_name,),
                    )
                    fk_rows = cur.fetchall() or []
                    fk_map: Dict[str, Dict[str, str]] = {}
                    for r in fk_rows:
                        col = r.get("column_name")
                        if not col:
                            continue
                        fk_map[col] = {
                            "foreign_table": r.get("foreign_table"),
                            "foreign_column": r.get("foreign_column"),
                        }

                    columns: List[Dict[str, Any]] = []
                    for c in cols:
                        cname = c.get("column_name")
                        col_out = {
                            "column_name": cname,
                            "data_type": c.get("data_type"),
                            "column_type": c.get("column_type"),
                            "is_nullable": (c.get("is_nullable") == "YES"),
                            "default": c.get("column_default"),
                            "ordinal_position": c.get("ordinal_position"),
                        }
                        if cname in pk_cols:
                            col_out["is_primary_key"] = True
                        if cname in fk_map:
                            col_out.update(fk_map[cname])
                        columns.append(col_out)

                    # Sample row (best-effort)
                    sample_data: List[Dict[str, Any]] = []
                    try:
                        quoted = _quote_identifier("mysql", table_name)
                        cur.execute(f"SELECT * FROM {quoted} LIMIT 1")
                        sample_rows = cur.fetchall() or []
                        sample_data = _serialize_rows(sample_rows)
                    except Exception:
                        sample_data = []

                    detailed_tables.append(
                        {
                            "success": True,
                            "name": table_name,
                            "type": table_row.get("table_type"),
                            "description": (table_row.get("table_description") or "").strip(),
                            "row_count_estimate": int(table_row.get("row_count") or 0),
                            "columns": columns,
                            "sample_data": sample_data,
                        }
                    )

                except Exception as e:
                    detailed_tables.append({"name": raw_name, "success": False, "error": str(e)})

        return {
            "success": True,
            "database_type": "mysql",
            "table_count": len(detailed_tables),
            "tables": detailed_tables,
        }
