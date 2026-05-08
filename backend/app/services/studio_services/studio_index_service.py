"""
Studio Index Service - Core CRUD for studio generation jobs via Supabase.

Educational Note: This service manages studio content generation jobs
(audio, video, presentations, etc.) in a Supabase `studio_jobs` table,
replacing the previous local studio_index.json file approach.

Job Status Flow:
    pending -> processing -> ready
                          -> error

The frontend polls the status endpoint to know when content is ready.

Architecture:
    This file provides generic CRUD (create_job, update_job, get_job,
    list_jobs, delete_job) that all 18 job modules delegate to.
    Each job module defines its own JOB_TYPE and default fields.

    jobs/
    ├── audio_jobs.py
    ├── video_jobs.py
    ├── ad_jobs.py
    ├── flash_card_jobs.py
    ├── mind_map_jobs.py
    ├── quiz_jobs.py
    ├── social_post_jobs.py
    ├── infographic_jobs.py
    ├── email_jobs.py
    ├── website_jobs.py
    ├── component_jobs.py
    ├── flow_diagram_jobs.py
    ├── wireframe_jobs.py
    ├── presentation_jobs.py
    ├── prd_jobs.py
    ├── marketing_strategy_jobs.py
    ├── blog_jobs.py
    └── business_report_jobs.py
"""
import logging
from typing import Dict, List, Any, Optional

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


# Top-level columns in the studio_jobs table (everything else goes into job_data JSONB)
_TOP_COLUMNS = {
    "status", "progress", "error_message", "started_at", "completed_at",
    "source_name", "direction", "source_id",
}


def _get_client():
    """Get Supabase client, raising error if not configured."""
    if not is_supabase_enabled():
        raise RuntimeError("Supabase is not configured.")
    return get_supabase()


def _map_job(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Flatten a Supabase row back to the dict format job modules expect.

    Educational Note: The studio_jobs table stores type-specific fields in a
    JSONB column (job_data). This function merges those back into the top-level
    dict so callers see the same flat structure they had with the old JSON files.
    """
    if not row:
        return None
    result = {**row}
    job_data = result.pop("job_data", {}) or {}
    result.update(job_data)
    # Rename error_message -> error for backwards compat with modules that use "error"
    if "error_message" in result and "error" not in result:
        result["error"] = result.pop("error_message")
    return result


def create_job(
    project_id: str,
    job_type: str,
    job_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Insert a new studio job into Supabase.

    Args:
        project_id: The project UUID
        job_type: Job type string (e.g., 'audio', 'video')
        job_data: All job fields — top-level columns are extracted,
                  everything else goes into the JSONB job_data column

    Returns:
        The created job record (flattened) or None on failure
    """
    try:
        client = _get_client()

        # Extract top-level columns from job_data
        row = {
            "project_id": project_id,
            "job_type": job_type,
            "id": job_data.pop("id"),
            "source_id": job_data.pop("source_id", None) or None,
            "source_name": job_data.pop("source_name", None),
            "direction": job_data.pop("direction", None),
            "status": job_data.pop("status", "pending"),
            "progress": job_data.pop("progress", None),
            "error_message": job_data.pop("error", job_data.pop("error_message", None)),
            "started_at": job_data.pop("started_at", None),
            "completed_at": job_data.pop("completed_at", None),
        }

        # Remove fields the DB manages automatically
        job_data.pop("created_at", None)
        job_data.pop("updated_at", None)

        # Everything remaining goes into job_data JSONB
        row["job_data"] = job_data

        response = client.table("studio_jobs").insert(row).execute()
        return _map_job(response.data[0]) if response.data else None
    except Exception as e:
        logger.error("Failed to create studio job (type=%s, project=%s): %s", job_type, project_id, e)
        return None


def update_job(
    project_id: str,
    job_id: str,
    **updates
) -> Optional[Dict[str, Any]]:
    """
    Update a studio job.

    Args:
        project_id: The project UUID
        job_id: The job UUID
        **updates: Fields to update — top-level columns update directly,
                   other fields merge into job_data JSONB

    Returns:
        Updated job record (flattened) or None if not found
    """
    try:
        client = _get_client()

        # Separate top-level columns from job_data fields
        top_level = {}
        job_data_updates = {}

        for k, v in updates.items():
            if v is not None:
                if k == "error":
                    # Map "error" back to "error_message" column
                    top_level["error_message"] = v
                elif k in _TOP_COLUMNS:
                    top_level[k] = v
                else:
                    job_data_updates[k] = v

        # Merge job_data updates via fetch-merge-update
        if job_data_updates:
            current = get_job(project_id, job_id)
            if not current:
                return None
            # Rebuild current job_data (fields not in top-level columns)
            current_job_data = {}
            for k, v in current.items():
                if k not in _TOP_COLUMNS and k not in {
                    "id", "project_id", "job_type", "created_at",
                    "updated_at", "error", "error_message", "job_data",
                }:
                    current_job_data[k] = v
            merged = {**current_job_data, **job_data_updates}
            top_level["job_data"] = merged

        if not top_level:
            return get_job(project_id, job_id)

        response = (
            client.table("studio_jobs")
            .update(top_level)
            .eq("id", job_id)
            .eq("project_id", project_id)
            .execute()
        )
        return _map_job(response.data[0]) if response.data else None
    except Exception as e:
        logger.error("Failed to update studio job %s: %s", job_id, e)
        return None


_TERMINAL_STATUSES = {"ready", "error", "cancelled"}


def with_failure_guard(callable_func):
    """
    Wrap a studio-job entry function with an exception safety net.

    Studio services run in background threads (task_service.submit_task).
    If an unhandled exception escapes the entry function, the studio_jobs
    row stays in `status="processing"` forever and the frontend polls it
    until pollJobStatus times out (~10 min) — that's the "stuck spinner"
    bug. This wrapper catches any exception, flips the row to
    `status="error"` so the frontend stops polling immediately, then
    re-raises so task_service still marks the background_tasks row failed
    for observability.

    Expects `project_id` and `job_id` to be present in kwargs (the
    convention every `submit_task` call uses for studio jobs).
    """
    from datetime import datetime

    def wrapped(*args, **kwargs):
        project_id = kwargs.get("project_id")
        job_id = kwargs.get("job_id")
        try:
            return callable_func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — re-raised below
            logger.exception(
                "Studio job %s (%s) crashed: %s",
                job_id, getattr(callable_func, "__name__", "unknown"), exc,
            )
            if project_id and job_id:
                try:
                    update_job(
                        project_id, job_id,
                        status="error",
                        error=f"Generation failed: {exc}",
                        completed_at=datetime.now().isoformat(),
                    )
                except Exception:
                    logger.exception(
                        "Failed to mark studio job %s as error after crash", job_id,
                    )
            raise

    wrapped.__name__ = getattr(callable_func, "__name__", "wrapped_studio_job")
    wrapped.__qualname__ = getattr(callable_func, "__qualname__", wrapped.__name__)
    return wrapped


def append_partial_image(
    project_id: str,
    job_id: str,
    url: str,
) -> Optional[Dict[str, Any]]:
    """
    Append a partial-image URL to a studio job's `partial_images` list.

    Used by the GPT Image 2 streaming path: each partial frame is uploaded
    to Supabase storage and its URL appended here. Frontend polls the job
    record and renders the partial frames as a live preview while the
    final image is still rendering.

    Bails out without writing when the job has already reached a terminal
    status. update_job's job_data path is fetch-merge-update of the entire
    JSONB column, so a late stream event can otherwise overwrite the
    finalized `images` array. Once the job is done, partial UX is
    irrelevant — drop the write.
    """
    if not url:
        return None
    current = get_job(project_id, job_id)
    if not current:
        return None
    if current.get("status") in _TERMINAL_STATUSES:
        return current
    partials = list(current.get("partial_images") or [])
    partials.append(url)
    return update_job(project_id, job_id, partial_images=partials)


def get_job(
    project_id: str,
    job_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a single studio job.

    Args:
        project_id: The project UUID
        job_id: The job UUID

    Returns:
        Job record (flattened) or None if not found
    """
    try:
        client = _get_client()
        response = (
            client.table("studio_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("project_id", project_id)
            .execute()
        )
        return _map_job(response.data[0]) if response.data else None
    except Exception as e:
        logger.error("Failed to get studio job %s: %s", job_id, e)
        return None


def list_jobs(
    project_id: str,
    job_type: str,
    source_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List studio jobs by type, optionally filtered by source.

    Args:
        project_id: The project UUID
        job_type: Job type string
        source_id: Optional source UUID to filter by

    Returns:
        List of job records (flattened), newest first
    """
    try:
        client = _get_client()
        query = (
            client.table("studio_jobs")
            .select("*")
            .eq("project_id", project_id)
            .eq("job_type", job_type)
            .order("created_at", desc=True)
        )
        if source_id:
            query = query.eq("source_id", source_id)

        response = query.execute()
        return [_map_job(row) for row in (response.data or [])]
    except Exception as e:
        logger.error("Failed to list studio jobs (type=%s, project=%s): %s", job_type, project_id, e)
        return []


def list_jobs_grouped(project_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    List all studio jobs for a project, grouped by job_type.

    Educational Note: This supports Studio bootstrap without issuing one
    request per section. Callers can filter by source client-side.
    """
    try:
        client = _get_client()
        response = (
            client.table("studio_jobs")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in (response.data or []):
            mapped = _map_job(row)
            if not mapped:
                continue
            job_type = mapped.get("job_type")
            if not job_type:
                continue
            grouped.setdefault(job_type, []).append(mapped)
        return grouped
    except Exception as e:
        logger.error("Failed to list grouped studio jobs (project=%s): %s", project_id, e)
        return {}


def delete_job(
    project_id: str,
    job_id: str
) -> bool:
    """
    Delete a studio job.

    Args:
        project_id: The project UUID
        job_id: The job UUID

    Returns:
        True if a row was deleted
    """
    try:
        client = _get_client()
        response = (
            client.table("studio_jobs")
            .delete()
            .eq("id", job_id)
            .eq("project_id", project_id)
            .execute()
        )
        return bool(response.data)
    except Exception as e:
        logger.error("Failed to delete studio job %s: %s", job_id, e)
        return False


# =============================================================================
# Re-exports for Backward Compatibility
# =============================================================================
# All job-specific functions are now in separate modules under jobs/
# These re-exports ensure existing imports continue to work.

from app.services.studio_services.jobs.audio_jobs import (
    create_audio_job,
    update_audio_job,
    get_audio_job,
    list_audio_jobs,
    delete_audio_job,
)

from app.services.studio_services.jobs.video_jobs import (
    create_video_job,
    update_video_job,
    get_video_job,
    list_video_jobs,
    delete_video_job,
)

from app.services.studio_services.jobs.ad_jobs import (
    create_ad_job,
    update_ad_job,
    get_ad_job,
    list_ad_jobs,
    delete_ad_job,
)

from app.services.studio_services.jobs.flash_card_jobs import (
    create_flash_card_job,
    update_flash_card_job,
    get_flash_card_job,
    list_flash_card_jobs,
    delete_flash_card_job,
)

from app.services.studio_services.jobs.mind_map_jobs import (
    create_mind_map_job,
    update_mind_map_job,
    get_mind_map_job,
    list_mind_map_jobs,
    delete_mind_map_job,
)

from app.services.studio_services.jobs.quiz_jobs import (
    create_quiz_job,
    update_quiz_job,
    get_quiz_job,
    list_quiz_jobs,
    delete_quiz_job,
)

from app.services.studio_services.jobs.social_post_jobs import (
    create_social_post_job,
    update_social_post_job,
    get_social_post_job,
    list_social_post_jobs,
    delete_social_post_job,
)

from app.services.studio_services.jobs.infographic_jobs import (
    create_infographic_job,
    update_infographic_job,
    get_infographic_job,
    list_infographic_jobs,
    delete_infographic_job,
)

from app.services.studio_services.jobs.email_jobs import (
    create_email_job,
    update_email_job,
    get_email_job,
    list_email_jobs,
    delete_email_job,
)

from app.services.studio_services.jobs.website_jobs import (
    create_website_job,
    update_website_job,
    get_website_job,
    list_website_jobs,
    delete_website_job,
)

from app.services.studio_services.jobs.component_jobs import (
    create_component_job,
    update_component_job,
    get_component_job,
    list_component_jobs,
    delete_component_job,
)

from app.services.studio_services.jobs.flow_diagram_jobs import (
    create_flow_diagram_job,
    update_flow_diagram_job,
    get_flow_diagram_job,
    list_flow_diagram_jobs,
    delete_flow_diagram_job,
)

from app.services.studio_services.jobs.wireframe_jobs import (
    create_wireframe_job,
    update_wireframe_job,
    get_wireframe_job,
    list_wireframe_jobs,
    delete_wireframe_job,
)

from app.services.studio_services.jobs.presentation_jobs import (
    create_presentation_job,
    update_presentation_job,
    get_presentation_job,
    list_presentation_jobs,
    delete_presentation_job,
)

from app.services.studio_services.jobs.prd_jobs import (
    create_prd_job,
    update_prd_job,
    get_prd_job,
    list_prd_jobs,
    delete_prd_job,
)

from app.services.studio_services.jobs.marketing_strategy_jobs import (
    create_marketing_strategy_job,
    update_marketing_strategy_job,
    get_marketing_strategy_job,
    list_marketing_strategy_jobs,
    delete_marketing_strategy_job,
)

from app.services.studio_services.jobs.blog_jobs import (
    create_blog_job,
    update_blog_job,
    get_blog_job,
    list_blog_jobs,
    delete_blog_job,
)

from app.services.studio_services.jobs.business_report_jobs import (
    create_business_report_job,
    update_business_report_job,
    get_business_report_job,
    list_business_report_jobs,
    delete_business_report_job,
)
