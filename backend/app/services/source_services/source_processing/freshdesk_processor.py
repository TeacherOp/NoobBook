"""
Freshdesk Processor - Handles FRESHDESK source processing.

Educational Note: Freshdesk tickets are stored globally (not per-source).
Processing checks if global tickets already exist — if so, it skips the
sync and just builds the summary. Only the first Freshdesk source triggers
a full API sync. Subsequent projects get instant access to existing data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.services.ai_services.summary_service import summary_service
from app.services.integrations.freshdesk.freshdesk_sync_service import (
    freshdesk_sync_service,
)
from app.services.integrations.supabase import get_supabase, storage_service

logger = logging.getLogger(__name__)


def _load_raw_metadata(raw_file_path: Path) -> Dict[str, Any]:
    """Load `.freshdesk` raw metadata JSON."""
    try:
        with open(raw_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_processed_text(
    source_name: str,
    captured_at: str,
    sync_stats: Dict[str, int],
    ticket_stats: Dict[str, Any],
) -> str:
    """
    Build processed text summary of the synced Freshdesk data.

    Educational Note: This text is stored in Supabase processed-files bucket
    and displayed in the Sources UI as a quick overview of the Freshdesk data.
    """
    header_lines = [
        f"# Extracted from FRESHDESK source: {source_name}",
        "# Type: FRESHDESK",
        f"# Captured at: {captured_at}",
        "# ---",
        "",
    ]

    lines = [
        "## Freshdesk Tickets Summary",
        "",
        f"Total tickets synced: {ticket_stats.get('ticket_count', 0)}",
        "",
    ]

    # Sync stats
    lines.append("### Sync Results")
    lines.append(f"- Tickets fetched: {sync_stats.get('tickets_fetched', 0)}")
    lines.append(f"- Tickets created: {sync_stats.get('tickets_created', 0)}")
    lines.append(f"- Tickets updated: {sync_stats.get('tickets_updated', 0)}")
    lines.append(f"- Errors: {sync_stats.get('errors', 0)}")
    lines.append("")

    # Status breakdown
    status_breakdown = ticket_stats.get("status_breakdown", {})
    if status_breakdown:
        lines.append("### Status Breakdown")
        for status, count in sorted(status_breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"- {status}: {count}")
        lines.append("")

    # Date range
    date_range = ticket_stats.get("date_range", {})
    earliest = date_range.get("earliest")
    latest = date_range.get("latest")
    if earliest or latest:
        lines.append("### Date Range")
        if earliest:
            lines.append(f"- Earliest ticket: {earliest}")
        if latest:
            lines.append(f"- Latest ticket: {latest}")
        lines.append("")

    lines.append(
        "Tip: Use the Freshdesk analysis agent in chat to ask questions "
        "about your ticket data (trends, metrics, breakdowns, etc.)."
    )
    lines.append("")

    return "\n".join(header_lines + lines)


def process_freshdesk(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service,
) -> Dict[str, Any]:
    """
    Process a FRESHDESK source:
    1) Load raw metadata (.freshdesk)
    2) Sync tickets from Freshdesk API into local table
    3) Build processed text summary
    4) Generate AI summary
    5) Mark source ready (skip embedding — queries go through analysis agent)
    """
    captured_at = datetime.now().isoformat()

    embedding_info = source.get("embedding_info", {}) or {}
    raw_meta = _load_raw_metadata(raw_file_path)

    days_back = embedding_info.get("days_back") or raw_meta.get("days_back") or 90

    # Step 1: Check if global tickets already exist (skip sync if so)
    existing_stats = freshdesk_sync_service.get_sync_stats()
    existing_count = existing_stats.get("ticket_count", 0)

    if existing_count > 0:
        logger.info(
            "Freshdesk processor: %d global tickets exist, skipping sync (source_id=%s)",
            existing_count, source_id,
        )
        sync_stats = {
            "tickets_fetched": 0, "tickets_created": 0,
            "tickets_updated": 0, "errors": 0,
            "skipped": True, "existing_count": existing_count,
        }
        ticket_stats = existing_stats
    else:
        # First time: sync tickets from Freshdesk API
        logger.info(
            "Freshdesk processor: syncing tickets (source_id=%s, days_back=%d)",
            source_id, days_back,
        )
        try:
            sync_stats = freshdesk_sync_service.sync_tickets(
                project_id=project_id,
                source_id=source_id,
                mode="backfill",
                days_back=days_back,
            )
        except Exception as e:
            source_service.update_source(
                project_id, source_id, status="error",
                processing_info={"error": f"Failed to sync Freshdesk tickets: {str(e)}"},
            )
            return {"success": False, "error": str(e)}

        # Check for fatal sync errors
        if sync_stats.get("tickets_fetched", 0) == 0 and sync_stats.get("errors", 0) > 0:
            error_msg = sync_stats.get("error_message", "Failed to fetch any tickets from Freshdesk")
            source_service.update_source(
                project_id, source_id, status="error",
                processing_info={"error": error_msg},
            )
            return {"success": False, "error": error_msg}

        ticket_stats = freshdesk_sync_service.get_sync_stats()

    # Step 3: Build processed text
    processed_text = _build_processed_text(
        source_name=source.get("name", "Freshdesk Tickets"),
        captured_at=captured_at,
        sync_stats=sync_stats,
        ticket_stats=ticket_stats,
    )

    # Upload processed text
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
            processing_info={"error": "Failed to upload processed summary"},
        )
        return {"success": False, "error": "Failed to upload processed file"}

    processing_info = {
        "processor": "freshdesk_ticket_sync",
        "captured_at": captured_at,
        "days_back": days_back,
        "tickets_synced": ticket_stats.get("ticket_count", 0),
        "sync_stats": sync_stats,
    }

    # Skip embedding — Freshdesk sources are queried via the dedicated
    # analyze_freshdesk_agent tool, not through RAG search_sources.
    merged_embedding_info = {
        **embedding_info,
        "is_embedded": False,
        "file_extension": ".freshdesk",
    }

    # Step 4: Summarize (AI)
    summary_info: Dict[str, Any] = {}
    try:
        summary_source_metadata = {
            "name": source.get("name", "Freshdesk Tickets"),
            "category": "freshdesk",
            "file_extension": ".freshdesk",
            "embedding_info": merged_embedding_info,
            "processing_info": {
                **processing_info,
                "total_pages": max(1, ticket_stats.get("ticket_count", 0)),
            },
        }
        summary_info = (
            summary_service.generate_summary(
                project_id, source_id, summary_source_metadata
            )
            or {}
        )
    except Exception as e:
        logger.exception("Summary generation failed for source %s", source_id)
        summary_info = {}

    # Step 5: Mark ready
    source_service.update_source(
        project_id,
        source_id,
        status="ready",
        processing_info=processing_info,
        embedding_info=merged_embedding_info,
        summary_info=summary_info if summary_info else None,
    )

    # Step 6: Start auto-sync (incremental every 15 minutes)
    freshdesk_sync_service.start_auto_sync(project_id, source_id)

    return {"success": True, "status": "ready"}
