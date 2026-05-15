"""
Saved Insights Service — CRUD + refresh for user-saved chat prompts that
auto-rerun on a daily / weekly cadence.

A "refresh" means: start a fresh single-turn chat in the same project,
send the saved prompt as the first user message, capture the assistant's
final text, and store it on the insight row. Subsequent reads return
the stored result without replaying the chat.

The `is_running` flag on each row is the scheduler's claim primitive:
`UPDATE saved_insights SET is_running = true WHERE id = ? AND NOT is_running`
either claims or fails atomically, so two parallel scheduler ticks can't
both fire the same insight.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.integrations.supabase import get_supabase

logger = logging.getLogger(__name__)


CADENCE_INTERVALS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


class InsightService:
    TABLE = "saved_insights"

    @property
    def supabase(self):
        return get_supabase()

    # ----- CRUD --------------------------------------------------------

    def list_insights(self, project_id: str, user_id: str) -> List[Dict[str, Any]]:
        response = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("project_id", project_id)
            .eq("owner_user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    def create_insight(
        self,
        *,
        project_id: str,
        owner_user_id: str,
        title: str,
        prompt: str,
        cadence: str,
    ) -> Dict[str, Any]:
        if cadence not in CADENCE_INTERVALS:
            raise ValueError(f"Invalid cadence {cadence!r}; expected 'daily' or 'weekly'")
        row = {
            "project_id": project_id,
            "owner_user_id": owner_user_id,
            "title": title.strip() or prompt[:60].strip(),
            "prompt": prompt.strip(),
            "cadence": cadence,
        }
        response = self.supabase.table(self.TABLE).insert(row).execute()
        if not response.data:
            raise RuntimeError("Failed to create saved insight")
        return response.data[0]

    def get_insight(self, insight_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("id", insight_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def delete_insight(self, insight_id: str, user_id: str) -> bool:
        # Owner check at the SQL level so we don't need to round-trip first.
        response = (
            self.supabase.table(self.TABLE)
            .delete()
            .eq("id", insight_id)
            .eq("owner_user_id", user_id)
            .execute()
        )
        return bool(response.data)

    # ----- Scheduler primitives ---------------------------------------

    def find_due_insights(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        """Return rows whose cadence interval has elapsed since last_run_at.

        Done in Python rather than SQL because Supabase REST doesn't let us
        compare two intervals against each other inline, and the row count
        is small (saved insights are deliberately user-scoped).
        """
        now = datetime.now(timezone.utc)
        response = (
            self.supabase.table(self.TABLE)
            .select("*")
            .eq("is_running", False)
            .limit(500)
            .execute()
        )
        rows = response.data or []
        due: List[Dict[str, Any]] = []
        for row in rows:
            # Check the cap first so the limit is enforced uniformly across
            # every path that might append (null last_run_at, parse error,
            # interval elapsed). A fresh deployment with hundreds of unrun
            # insights would otherwise blow past `limit` and saturate the
            # scheduler's thread pool.
            if len(due) >= limit:
                break
            interval = CADENCE_INTERVALS.get(row.get("cadence"))
            if interval is None:
                continue
            last = row.get("last_run_at")
            if last is None:
                due.append(row)
                continue
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                due.append(row)
                continue
            if now - last_dt >= interval:
                due.append(row)
        return due

    def claim_for_refresh(self, insight_id: str) -> bool:
        """Atomic claim: set is_running=true only if currently false.

        Supabase Python SDK doesn't expose RETURNING for UPDATE ... WHERE
        easily, so we do the read-then-write with a guard. Race-safe because
        we filter on `is_running=False` in the WHERE — concurrent claims
        will both UPDATE but only the row already-flagged-false will match;
        the loser's UPDATE returns empty data and we know we didn't claim.
        """
        response = (
            self.supabase.table(self.TABLE)
            .update({"is_running": True})
            .eq("id", insight_id)
            .eq("is_running", False)
            .execute()
        )
        return bool(response.data)

    def reset_stale_claims(self, *, grace_minutes: int = 30) -> int:
        """Clear `is_running` on rows abandoned by a crashed worker.

        Why: `refresh_insight` sets `is_running=true`, runs the chat, then
        clears it. If the container is SIGKILLed (Coolify redeploy, OOM,
        watchdog bounce) between those steps the flag stays stuck on the
        row and the scheduler will skip it forever. We sweep on startup
        and clear anything claimed longer than the grace window.

        Returns the number of rows reset.
        """
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=grace_minutes)).isoformat()
        response = (
            self.supabase.table(self.TABLE)
            .update({
                "is_running": False,
                "last_error": "Refresh interrupted by server restart",
            })
            .eq("is_running", True)
            .lt("updated_at", cutoff)
            .execute()
        )
        rows = response.data or []
        if rows:
            logger.info("Insight scheduler: reset %d stale claim(s)", len(rows))
        return len(rows)

    def release_with_result(
        self,
        insight_id: str,
        *,
        result_text: Optional[str],
        chat_id: Optional[str],
    ) -> None:
        """Stamp a successful refresh result and clear the running flag."""
        self.supabase.table(self.TABLE).update(
            {
                "is_running": False,
                "last_run_at": datetime.now(timezone.utc).isoformat(),
                "last_result": result_text,
                "last_chat_id": chat_id,
                "last_error": None,
            }
        ).eq("id", insight_id).execute()

    def release_with_error(self, insight_id: str, *, error_text: str) -> None:
        """Clear the running flag after a failed refresh, leaving last_run_at
        untouched so the next scheduler tick retries immediately instead of
        postponing by a full cadence interval."""
        self.supabase.table(self.TABLE).update(
            {
                "is_running": False,
                "last_error": error_text[:500],
            }
        ).eq("id", insight_id).execute()

    # ----- Refresh -----------------------------------------------------

    def refresh_insight(self, insight_id: str) -> Dict[str, Any]:
        """Re-run the saved prompt as a fresh chat and store the result.

        Caller may have already claimed the row (scheduler path) or not
        (manual /refresh route). Either way the entire body runs under a
        single try/except so a transient Supabase error before send_message
        — or any other unexpected failure — can never leave `is_running=true`
        permanently. On failure we keep `last_run_at` untouched so the next
        scheduler tick retries on the very next cycle instead of waiting a
        full cadence interval.
        """
        # Local imports to avoid a circular import at module load:
        # chat_service / main_chat_service both pull data_services in.
        from app.services.data_services import chat_service
        from app.services.chat_services.main_chat_service import main_chat_service

        chat_id: Optional[str] = None
        try:
            # Defensive claim — no-op if already claimed by caller.
            self.claim_for_refresh(insight_id)

            insight = self.get_insight(insight_id)
            if not insight:
                # Released via the error helper so the caller still gets a
                # consistent {success: False, ...} response; if the row is
                # genuinely missing the UPDATE is just a no-op.
                self.release_with_error(insight_id, error_text="Insight not found")
                return {"success": False, "error": "Insight not found"}

            project_id = insight["project_id"]
            prompt = insight["prompt"]

            # Fresh chat per refresh keeps the runs auditable and avoids
            # any context carry-over from previous turns.
            chat = chat_service.create_chat(
                project_id,
                title=f"Insight refresh: {insight['title'][:50]}",
            )
            chat_id = chat["id"]

            result = main_chat_service.send_message(
                project_id=project_id,
                chat_id=chat_id,
                user_message_text=prompt,
            )

            assistant_text = _extract_assistant_text(result.get("assistant_message"))
            self.release_with_result(
                insight_id,
                result_text=assistant_text,
                chat_id=chat_id,
            )
            return {"success": True, "result": assistant_text, "chat_id": chat_id}

        except Exception as exc:
            logger.exception("Failed to refresh insight %s: %s", insight_id, exc)
            try:
                self.release_with_error(insight_id, error_text=str(exc))
            except Exception as release_exc:
                # If even the cleanup write fails the row stays claimed; the
                # startup reaper will eventually unstick it. Log loudly so
                # we notice in metrics.
                logger.exception(
                    "Failed to release insight %s after error: %s",
                    insight_id,
                    release_exc,
                )
            return {"success": False, "error": str(exc)}


def _extract_assistant_text(assistant_message: Optional[Dict[str, Any]]) -> Optional[str]:
    """Pull plain text out of an assistant message regardless of content shape."""
    if not assistant_message:
        return None
    content = assistant_message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts) if parts else None
    return None


insight_service = InsightService()
