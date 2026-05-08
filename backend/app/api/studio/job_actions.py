"""
Studio Job Actions — generic actions on a studio_jobs row, regardless of
job_type. Currently exposes a `cancel` action used by the ActiveTasksBar
Stop button.

Cancellation semantics in v1:
- The job's status is flipped to "cancelled" immediately.
- The active-tasks endpoint filters by status in {pending, processing},
  so the job disappears from the user's status bar straight away.
- The background worker doesn't have cooperative-cancel hooks today, so
  it may continue running until completion. When it eventually calls
  update_job(status="ready"), the cancelled marker can get overwritten —
  acceptable for v1 because the user-facing affordance (it stops showing
  in the bar) already feels like "cancelled". Future v2: plumb a
  cancel_event into the worker the same way main_chat_service does.

Idempotent: re-requesting cancel on an already-terminal job returns 200
with the current state — saves the frontend from racing the user's
double-click.
"""
from datetime import datetime

from flask import current_app, jsonify

from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service


_TERMINAL_STATUSES = {"ready", "error", "cancelled"}


@studio_bp.route(
    "/projects/<project_id>/studio/jobs/<job_id>/cancel",
    methods=["POST"],
)
def cancel_studio_job(project_id: str, job_id: str):
    """Cancel an in-flight studio job."""
    try:
        job = studio_index_service.get_job(project_id, job_id)
        if not job:
            return jsonify({
                "success": False,
                "error": f"Job not found: {job_id}",
            }), 404

        current_status = job.get("status")
        if current_status in _TERMINAL_STATUSES:
            # Already done one way or another — return current state so the
            # caller can update its UI without a 4xx.
            return jsonify({"success": True, "job": job, "already_terminal": True}), 200

        updated = studio_index_service.update_job(
            project_id,
            job_id,
            status="cancelled",
            error="Cancelled by user",
            completed_at=datetime.now().isoformat(),
        )
        if not updated:
            return jsonify({
                "success": False,
                "error": "Failed to mark job as cancelled.",
            }), 500

        return jsonify({"success": True, "job": updated}), 200
    except Exception as e:
        current_app.logger.error(
            f"Error cancelling studio job {job_id} (project {project_id}): {e}"
        )
        return jsonify({"success": False, "error": str(e)}), 500
