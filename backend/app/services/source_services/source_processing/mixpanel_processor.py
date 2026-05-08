"""
Mixpanel Processor - Handles MIXPANEL source processing.

Educational Note: Lightweight verifier. Confirms the Mixpanel Query API is
reachable with the configured Service Account, fetches a sample of tracked
event names for the summary, and marks the source ready. All real queries
happen live via the chat tools (mixpanel_list_events, mixpanel_query_events,
mixpanel_segmentation, mixpanel_funnel, mixpanel_retention, mixpanel_events_after).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.services.ai_services.summary_service import summary_service
from app.services.integrations.knowledge_bases.mixpanel.mixpanel_service import mixpanel_service
from app.services.integrations.supabase import storage_service

logger = logging.getLogger(__name__)


def _build_processed_text(
    source_name: str,
    captured_at: str,
    event_count: int,
    event_names: list[str],
) -> str:
    """Build processed text summary of the connected Mixpanel project."""
    header_lines = [
        f"# Extracted from MIXPANEL source: {source_name}",
        "# Type: MIXPANEL",
        f"# Captured at: {captured_at}",
        "# ---",
        "",
    ]

    lines = [
        "## Mixpanel Connection Summary",
        "",
        f"Total event names tracked: {event_count}",
        "",
    ]

    if event_names:
        lines.append("### Sample Events")
        for name in event_names[:30]:
            lines.append(f"- {name}")
        if event_count > 30:
            lines.append(f"- ... and {event_count - 30} more")
        lines.append("")

    lines.append(
        "Tip: Use mixpanel_list_events, mixpanel_query_events, mixpanel_segmentation, "
        "mixpanel_list_funnels, mixpanel_query_funnel, mixpanel_retention, and "
        "mixpanel_events_after (cohort path analysis: 'what do users do after X') "
        "tools in chat for live analytics queries."
    )
    lines.append("")

    return "\n".join(header_lines + lines)


def process_mixpanel(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service,
) -> Dict[str, Any]:
    """
    Process a MIXPANEL source:
    1) Verify Mixpanel Query API connection
    2) Fetch a sample of event names for the summary
    3) Generate AI summary
    4) Mark ready (no embedding — queries go through live API tools)
    """
    captured_at = datetime.now().isoformat()
    embedding_info = source.get("embedding_info", {}) or {}

    try:
        result = mixpanel_service.list_events(limit=100)
    except Exception as e:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": f"Failed to connect to Mixpanel: {str(e)}"},
        )
        return {"success": False, "error": str(e)}

    if not result.get("success"):
        error_msg = result.get("error", "Failed to connect to Mixpanel API")
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": error_msg},
        )
        return {"success": False, "error": error_msg}

    events = result.get("events", [])
    event_count = result.get("total", len(events))

    processed_text = _build_processed_text(
        source_name=source.get("name", "Mixpanel Analytics"),
        captured_at=captured_at,
        event_count=event_count,
        event_names=events,
    )

    processed_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=processed_text,
    )
    if not processed_path:
        source_service.update_source(
            project_id, source_id, status="error",
            processing_info={"error": "Failed to upload processed summary"},
        )
        return {"success": False, "error": "Failed to upload processed file"}

    processing_info = {
        "processor": "mixpanel_connection_verify",
        "captured_at": captured_at,
        "events_found": event_count,
    }

    merged_embedding_info = {
        **embedding_info,
        "is_embedded": False,
        "file_extension": ".mixpanel",
    }

    summary_info: Dict[str, Any] = {}
    try:
        summary_source_metadata = {
            "name": source.get("name", "Mixpanel Analytics"),
            "category": "mixpanel",
            "file_extension": ".mixpanel",
            "embedding_info": merged_embedding_info,
            "processing_info": {
                **processing_info,
                "total_pages": max(1, event_count),
            },
        }
        summary_info = (
            summary_service.generate_summary(
                project_id, source_id, summary_source_metadata
            )
            or {}
        )
    except Exception:
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
