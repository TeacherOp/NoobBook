"""
Studio Job Actions — generic actions on a studio_jobs row, regardless of
job_type. Currently exposes a `cancel` action used by the ActiveTasksBar
Stop button.

Cancellation flow (cooperative, full-fledged):
1. POST /cancel flips studio_jobs.status = "cancelled" so the
   active-tasks endpoint stops listing the row immediately.
2. The same route signals task_service.cancel_tasks_for_target(job_id)
   so the in-memory _cancelled_tasks set has the worker's task_id by the
   time the worker hits its next breakpoint.
3. Studio services scattered raise_if_cancelled(project_id, job_id) at
   their natural breakpoints (start, between loop iterations, before
   each external API call, before final persist). When any breakpoint
   trips, the service raises StudioJobCancelled and bails cleanly.
4. with_failure_guard catches StudioJobCancelled specifically and DOES
   NOT overwrite the cancelled marker with status="error".
5. update_job has belt-and-braces clobber-protection: refuses any non-
   cancelled status update when the current row is already cancelled.

Idempotent: re-requesting cancel on an already-terminal job (ready /
error / cancelled) returns 200 with the current state — saves the
frontend from racing the user's double-click.
"""
from datetime import datetime

from flask import current_app, jsonify

from app.api.studio import studio_bp
from app.services.background_services import task_service
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

        # 1. Flip the studio_jobs row first. The active-tasks endpoint
        #    filters by status in {pending, processing}, so the row drops
        #    out of the user's bar immediately on the next 3s poll.
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

        # 2. Signal the running worker via task_service so its in-memory
        #    is_target_cancelled() check trips on the very next breakpoint.
        #    Without this, the worker would only learn about the cancel
        #    via the DB row check inside studio_index_service.is_job_cancelled,
        #    which is fine but slower (one extra round-trip per breakpoint).
        cancelled_task_count = task_service.cancel_tasks_for_target(job_id)
        current_app.logger.info(
            "Cancelled studio job %s — %d background task(s) signalled",
            job_id, cancelled_task_count,
        )

        return jsonify({
            "success": True,
            "job": updated,
            "tasks_signalled": cancelled_task_count,
        }), 200
    except Exception as e:
        current_app.logger.error(
            f"Error cancelling studio job {job_id} (project {project_id}): {e}"
        )
        return jsonify({"success": False, "error": str(e)}), 500
