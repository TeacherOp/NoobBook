"""
Task Repository Interface - Contract for background task data access.

Educational Note: Tasks track background operations like source processing.
The TaskService uses ThreadPoolExecutor for execution; this repository
handles the persistence layer.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class TaskRepositoryInterface(ABC):
    """Interface for task repository operations."""

    @abstractmethod
    def create(
        self,
        task_type: str,
        target_id: str
    ) -> Dict[str, Any]:
        """
        Create a new task record.

        Args:
            task_type: Type of task (e.g., "source_processing")
            target_id: ID of the target resource

        Returns:
            Created task record with id
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by ID.

        Args:
            task_id: The task UUID

        Returns:
            Task record or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_target(self, target_id: str) -> List[Dict[str, Any]]:
        """
        Get all tasks for a target resource.

        Args:
            target_id: The target resource ID

        Returns:
            List of task records
        """
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update task status.

        Args:
            task_id: The task UUID
            status: New status (pending, running, completed, failed, cancelled)
            error_message: Optional error message

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def mark_started(self, task_id: str) -> bool:
        """
        Mark task as started (running).

        Args:
            task_id: The task UUID

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def mark_completed(self, task_id: str) -> bool:
        """
        Mark task as completed.

        Args:
            task_id: The task UUID

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, task_id: str, error_message: str) -> bool:
        """
        Mark task as failed.

        Args:
            task_id: The task UUID
            error_message: The error message

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def mark_cancelled(self, task_id: str) -> bool:
        """
        Mark task as cancelled.

        Args:
            task_id: The task UUID

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all pending tasks.

        Returns:
            List of pending task records
        """
        raise NotImplementedError

    @abstractmethod
    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all running tasks.

        Returns:
            List of running task records
        """
        raise NotImplementedError

    @abstractmethod
    def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """
        Remove completed/failed tasks older than specified hours.

        Args:
            older_than_hours: Age threshold in hours

        Returns:
            Number of tasks removed
        """
        raise NotImplementedError

    @abstractmethod
    def mark_stale_as_failed(self) -> int:
        """
        Mark any running/pending tasks as failed (for server restart cleanup).

        Returns:
            Number of tasks marked as failed
        """
        raise NotImplementedError
