"""
JSON Task Repository - File-based implementation.

Educational Note: Tasks are stored in data/tasks/tasks_index.json.
This wraps the existing JSON storage for the TaskService.
"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import Config
from app.repositories.tasks.interface import TaskRepositoryInterface


class JsonTaskRepository(TaskRepositoryInterface):
    """JSON file-based implementation of task repository."""

    def __init__(self):
        """Initialize with tasks directory from config."""
        self.tasks_dir = Config.DATA_DIR / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.tasks_dir / "tasks_index.json"
        self._ensure_index()

    def _ensure_index(self) -> None:
        """Ensure the tasks index file exists."""
        if not self.index_path.exists():
            self._save_index({"tasks": [], "last_updated": datetime.now().isoformat()})

    def _load_index(self) -> Dict[str, Any]:
        """Load the tasks index from JSON file."""
        try:
            with open(self.index_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"tasks": [], "last_updated": datetime.now().isoformat()}

    def _save_index(self, data: Dict[str, Any]) -> None:
        """Save the tasks index to JSON file."""
        data["last_updated"] = datetime.now().isoformat()
        with open(self.index_path, "w") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def create(self, task_type: str, target_id: str) -> Dict[str, Any]:
        """Create a new task record."""
        task_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        task_record = {
            "id": task_id,
            "type": task_type,
            "target_id": target_id,
            "status": "pending",
            "error": None,
            "created_at": timestamp,
            "started_at": None,
            "completed_at": None
        }

        index = self._load_index()
        index["tasks"].append(task_record)
        self._save_index(index)

        return task_record

    def get_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        index = self._load_index()
        for task in index["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def get_by_target(self, target_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a target resource."""
        index = self._load_index()
        return [t for t in index["tasks"] if t["target_id"] == target_id]

    def update_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update task status."""
        index = self._load_index()

        for task in index["tasks"]:
            if task["id"] == task_id:
                task["status"] = status
                if error_message:
                    task["error"] = error_message
                if status == "running" and not task.get("started_at"):
                    task["started_at"] = datetime.now().isoformat()
                if status in ("completed", "failed", "cancelled"):
                    task["completed_at"] = datetime.now().isoformat()

                self._save_index(index)
                return True

        return False

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
        index = self._load_index()
        return [t for t in index["tasks"] if t["status"] == "pending"]

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """Get all running tasks."""
        index = self._load_index()
        return [t for t in index["tasks"] if t["status"] == "running"]

    def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """Remove completed/failed tasks older than specified hours."""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        index = self._load_index()
        original_count = len(index["tasks"])

        index["tasks"] = [
            t for t in index["tasks"]
            if t["status"] in ["pending", "running"]
            or (
                t.get("completed_at")
                and datetime.fromisoformat(t["completed_at"]) > cutoff
            )
        ]

        removed_count = original_count - len(index["tasks"])
        if removed_count > 0:
            self._save_index(index)

        return removed_count

    def mark_stale_as_failed(self) -> int:
        """Mark running/pending tasks as failed (server restart cleanup)."""
        index = self._load_index()
        stale_count = 0

        for task in index["tasks"]:
            if task["status"] in ["pending", "running"]:
                task["status"] = "failed"
                task["error"] = "Server restarted while task was running"
                task["completed_at"] = datetime.now().isoformat()
                stale_count += 1

        if stale_count > 0:
            self._save_index(index)

        return stale_count
