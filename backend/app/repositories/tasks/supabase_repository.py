"""
Supabase Task Repository - PostgreSQL-based implementation.

Educational Note: Tasks are stored in the tasks table. Using PostgreSQL
provides better concurrency handling for task status updates compared
to JSON file locking.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.tasks.interface import TaskRepositoryInterface


class SupabaseTaskRepository(TaskRepositoryInterface):
    """Supabase/PostgreSQL implementation of task repository."""

    def __init__(self):
        """Initialize with Supabase client."""
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
            if self._client is None:
                raise RuntimeError("Supabase client not available")
        return self._client

    @property
    def table(self):
        """Get the tasks table reference."""
        return self.client.table("tasks")

    def _to_task_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to task format (matching JSON format)."""
        return {
            "id": row["id"],
            "type": row["task_type"],
            "target_id": row["target_id"],
            "status": row["status"],
            "error": row.get("error_message"),
            "created_at": row["created_at"],
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at")
        }

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def create(self, task_type: str, target_id: str) -> Dict[str, Any]:
        """Create a new task record."""
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        data = {
            "id": task_id,
            "task_type": task_type,
            "target_id": target_id,
            "status": "pending",
            "created_at": now
        }

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create task")

        return self._to_task_dict(result.data[0])

    def get_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        result = self.table.select("*").eq("id", task_id).execute()

        if not result.data:
            return None
        return self._to_task_dict(result.data[0])

    def get_by_target(self, target_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a target resource."""
        result = self.table.select("*").eq("target_id", target_id).execute()
        return [self._to_task_dict(row) for row in result.data]

    def update_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update task status."""
        updates = {"status": status}

        if error_message:
            updates["error_message"] = error_message
        if status == "running":
            updates["started_at"] = datetime.now().isoformat()
        if status in ("completed", "failed", "cancelled"):
            updates["completed_at"] = datetime.now().isoformat()

        result = self.table.update(updates).eq("id", task_id).execute()
        return len(result.data) > 0 if result.data else False

    def mark_started(self, task_id: str) -> bool:
        """Mark task as started."""
        return self.update_status(task_id, "running")

    def mark_completed(self, task_id: str) -> bool:
        """Mark task as completed."""
        return self.update_status(task_id, "completed")

    def mark_failed(self, task_id: str, error_message: str) -> bool:
        """Mark task as failed."""
        return self.update_status(task_id, "failed", error_message)

    def mark_cancelled(self, task_id: str) -> bool:
        """Mark task as cancelled."""
        return self.update_status(task_id, "cancelled", "Cancelled by user")

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks."""
        result = self.table.select("*").eq("status", "pending").execute()
        return [self._to_task_dict(row) for row in result.data]

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """Get all running tasks."""
        result = self.table.select("*").eq("status", "running").execute()
        return [self._to_task_dict(row) for row in result.data]

    def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """Remove completed/failed tasks older than specified hours."""
        cutoff = (datetime.now() - timedelta(hours=older_than_hours)).isoformat()

        # Delete old completed/failed tasks
        result = self.table.delete().in_(
            "status", ["completed", "failed", "cancelled"]
        ).lt("completed_at", cutoff).execute()

        return len(result.data) if result.data else 0

    def mark_stale_as_failed(self) -> int:
        """Mark running/pending tasks as failed (server restart cleanup)."""
        now = datetime.now().isoformat()

        result = self.table.update({
            "status": "failed",
            "error_message": "Server restarted while task was running",
            "completed_at": now
        }).in_("status", ["pending", "running"]).execute()

        return len(result.data) if result.data else 0
