"""
Saved Insights routes — list, create, delete, manual refresh.

The scheduler handles automatic refresh on cadence; this surface lets the
user save new insights, see what's stored, kick a refresh by hand, and
delete ones they no longer want.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from flask import current_app, jsonify, request

from app.api.insights import insights_bp
from app.services.auth.rbac import get_request_identity
from app.services.data_services import project_service
from app.services.data_services.insight_service import insight_service


def _project_access_or_404(project_id: str, user_id: str):
    """Enforce project membership before any insight mutation.

    The backend uses the Supabase service-role JWT for all writes, which
    bypasses RLS — so the project-ownership gate must live in Python,
    not in the database policy. Without this an authenticated user who
    knows a foreign project UUID could attach a scheduler-driven chat
    to it.
    """
    if not project_service.has_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    return None


# Reused worker pool for manual refreshes — keeps the response endpoint
# fast (returns immediately) while the refresh runs in the background.
_manual_refresh_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="insight-manual")


def _current_user_id() -> Optional[str]:
    identity = get_request_identity()
    return identity.user_id if identity.is_authenticated else None


@insights_bp.route("/projects/<project_id>/insights", methods=["GET"])
def list_insights(project_id: str):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    err = _project_access_or_404(project_id, user_id)
    if err is not None:
        return err
    try:
        rows = insight_service.list_insights(project_id, user_id)
        return jsonify({"success": True, "insights": rows}), 200
    except Exception as exc:
        current_app.logger.error("list_insights failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@insights_bp.route("/projects/<project_id>/insights", methods=["POST"])
def create_insight(project_id: str):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    err = _project_access_or_404(project_id, user_id)
    if err is not None:
        return err
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    cadence = (data.get("cadence") or "weekly").strip()
    title = (data.get("title") or prompt[:60]).strip()
    if not prompt:
        return jsonify({"success": False, "error": "Prompt is required"}), 400
    if cadence not in ("daily", "weekly"):
        return jsonify({"success": False, "error": "Cadence must be 'daily' or 'weekly'"}), 400
    try:
        insight = insight_service.create_insight(
            project_id=project_id,
            owner_user_id=user_id,
            title=title,
            prompt=prompt,
            cadence=cadence,
        )
        return jsonify({"success": True, "insight": insight}), 201
    except Exception as exc:
        current_app.logger.error("create_insight failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@insights_bp.route(
    "/projects/<project_id>/insights/<insight_id>", methods=["DELETE"]
)
def delete_insight(project_id: str, insight_id: str):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    err = _project_access_or_404(project_id, user_id)
    if err is not None:
        return err
    deleted = insight_service.delete_insight(insight_id, user_id)
    if not deleted:
        return jsonify({"success": False, "error": "Not found"}), 404
    return jsonify({"success": True}), 200


@insights_bp.route(
    "/projects/<project_id>/insights/<insight_id>/refresh", methods=["POST"]
)
def refresh_insight(project_id: str, insight_id: str):
    user_id = _current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    err = _project_access_or_404(project_id, user_id)
    if err is not None:
        return err

    insight = insight_service.get_insight(insight_id)
    if (
        not insight
        or insight.get("owner_user_id") != user_id
        or insight.get("project_id") != project_id
    ):
        return jsonify({"success": False, "error": "Not found"}), 404

    # Claim before submitting so we can return a clean 409 if a scheduler
    # tick or another tab already kicked off this refresh.
    if not insight_service.claim_for_refresh(insight_id):
        return jsonify(
            {"success": False, "error": "Refresh already in progress"}
        ), 409

    _manual_refresh_pool.submit(_run_manual_refresh, insight_id)
    return jsonify({"success": True, "status": "queued"}), 202


def _run_manual_refresh(insight_id: str) -> None:
    try:
        insight_service.refresh_insight(insight_id)
    except Exception:
        # refresh_insight already logs + records last_error; just swallow
        # so the worker pool doesn't surface this on stderr a second time.
        pass
