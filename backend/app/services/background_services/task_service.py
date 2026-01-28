"""
Task Service - Background task management using ThreadPoolExecutor.

Educational Note: This service manages background tasks without external
dependencies like Celery or Redis. It uses Python's built-in ThreadPoolExecutor
for concurrent execution and the repository layer for task tracking.

Why ThreadPoolExecutor works for our use case:
- Our tasks are I/O-bound (API calls, file operations)
- I/O operations release the GIL (Global Interpreter Lock)
- While one thread waits for Claude API, other threads can run
- User can chat while PDFs are being processed in background

How it works:
1. Task is submitted with a callable and arguments
2. ThreadPoolExecutor runs it in a background thread
3. Task status is tracked via repository
4. Source status is updated directly by the task
"""
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional, List

from app.repositories import get_task_repository


class TaskService:
    """
    Service class for managing background tasks.

    Educational Note: This is a simple task queue implementation using
    Python's built-in ThreadPoolExecutor. Task tracking is handled by
    the repository layer.
    """

    # Maximum concurrent background tasks
    MAX_WORKERS = 4

    def __init__(self):
        """Initialize the task service."""
        self._repo = None

        # Thread pool for executing tasks
        # Educational Note: ThreadPoolExecutor manages a pool of worker threads
        # Tasks are queued and executed as threads become available
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)

        # Lock for thread-safe operations
        self._lock = threading.Lock()

        # Track running futures (for potential cancellation)
        self._futures: Dict[str, Future] = {}

        # Track cancelled tasks - workers check this to stop early
        self._cancelled_tasks: set = set()

        # Clean up any stale tasks from previous runs
        self._cleanup_stale_tasks()

    @property
    def repo(self):
        """Lazy-load the repository."""
        if self._repo is None:
            self._repo = get_task_repository()
        return self._repo

    def _cleanup_stale_tasks(self) -> None:
        """
        Clean up tasks that were running when server stopped.

        Educational Note: If the server restarts while tasks are running,
        those tasks will be stuck in "running" or "pending" state forever.
        We mark them as failed on startup.
        """
        try:
            tasks = self.repo.list_all()
            stale_count = 0

            for task in tasks:
                if task["status"] in ["pending", "running"]:
                    self.repo.update(task["id"], {
                        "status": "failed",
                        "error": "Server restarted while task was running",
                        "completed_at": datetime.now().isoformat()
                    })
                    stale_count += 1

            if stale_count > 0:
                print(f"Marked {stale_count} stale tasks as failed")

        except Exception as e:
            print(f"Error cleaning up stale tasks: {e}")

    def submit_task(
        self,
        task_type: str,
        target_id: str,
        callable_func: Callable,
        *args,
        **kwargs
    ) -> str:
        """
        Submit a task for background execution.

        Educational Note: This method returns immediately after queuing the task.
        The actual execution happens in a background thread.

        Args:
            task_type: Type of task (e.g., "source_processing")
            target_id: ID of the target resource (e.g., source_id)
            callable_func: The function to execute
            *args, **kwargs: Arguments to pass to the function

        Returns:
            task_id: Unique identifier for tracking the task
        """
        # Create task record via repository
        task = self.repo.create(task_type=task_type, target_id=target_id)
        task_id = task["id"]

        # Wrapper function that handles status updates
        def task_wrapper():
            try:
                # Update status to running
                self.repo.update(task_id, {
                    "status": "running",
                    "started_at": datetime.now().isoformat()
                })

                # Execute the actual task
                result = callable_func(*args, **kwargs)

                # Update status to completed
                self.repo.update(task_id, {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat()
                })

                return result

            except Exception as e:
                # Update status to failed
                self.repo.update(task_id, {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now().isoformat()
                })
                print(f"Task {task_id} failed: {e}")

            finally:
                # Remove from futures tracking
                with self._lock:
                    self._futures.pop(task_id, None)
                    # Remove from cancelled set if present
                    self._cancelled_tasks.discard(task_id)

        # Submit to executor - this returns immediately
        future = self._executor.submit(task_wrapper)
        with self._lock:
            self._futures[task_id] = future

        print(f"Task submitted: {task_id} ({task_type} for {target_id})")

        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task's current status."""
        return self.repo.get_by_id(task_id)

    def get_tasks_for_target(self, target_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific target."""
        return self.repo.list_by_target(target_id)

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.

        Educational Note: Cancellation is cooperative - we set a flag that
        the running task should check periodically. For ThreadPoolExecutor,
        we can also try to cancel the future if it hasn't started yet.

        Args:
            task_id: The task ID to cancel

        Returns:
            True if cancellation was initiated, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        # Only cancel pending or running tasks
        if task["status"] not in ["pending", "running"]:
            return False

        # Add to cancelled set - workers should check this
        with self._lock:
            self._cancelled_tasks.add(task_id)

            # Try to cancel the future if it hasn't started yet
            future = self._futures.get(task_id)
            if future:
                cancelled = future.cancel()
                if cancelled:
                    print(f"Task {task_id} cancelled before it started")

        # Update task status
        self.repo.update(task_id, {
            "status": "cancelled",
            "error": "Cancelled by user",
            "completed_at": datetime.now().isoformat()
        })

        print(f"Task {task_id} cancellation requested")
        return True

    def is_cancelled(self, task_id: str) -> bool:
        """
        Check if a task has been cancelled.

        Educational Note: Long-running tasks should call this periodically
        and stop early if True. This enables cooperative cancellation.

        Args:
            task_id: The task ID to check

        Returns:
            True if task should stop, False otherwise
        """
        with self._lock:
            return task_id in self._cancelled_tasks

    def cancel_tasks_for_target(self, target_id: str) -> int:
        """
        Cancel all running/pending tasks for a target (e.g., a source).

        Args:
            target_id: The target resource ID

        Returns:
            Number of tasks cancelled
        """
        tasks = self.get_tasks_for_target(target_id)
        cancelled_count = 0

        for task in tasks:
            if task["status"] in ["pending", "running"]:
                if self.cancel_task(task["id"]):
                    cancelled_count += 1

        return cancelled_count

    def is_target_cancelled(self, target_id: str) -> bool:
        """
        Check if any task for a target has been cancelled.

        Educational Note: This is useful for long-running operations that
        need to check if they should stop early, but don't know their task_id.

        Args:
            target_id: The target resource ID (e.g., source_id)

        Returns:
            True if any task for this target was cancelled
        """
        tasks = self.get_tasks_for_target(target_id)
        with self._lock:
            for task in tasks:
                if task["id"] in self._cancelled_tasks:
                    return True
                # Also check if task status is cancelled
                if task["status"] == "cancelled":
                    return True
        return False

    def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """
        Remove completed/failed tasks older than specified hours.

        Educational Note: Call this periodically to prevent storage
        from growing indefinitely.

        Args:
            older_than_hours: Remove tasks completed more than this many hours ago

        Returns:
            Number of tasks removed
        """
        cutoff = datetime.now() - timedelta(hours=older_than_hours)

        tasks = self.repo.list_all()
        removed_count = 0

        for task in tasks:
            # Keep pending/running tasks
            if task["status"] in ["pending", "running"]:
                continue

            # Check if task is old enough to remove
            completed_at = task.get("completed_at")
            if completed_at:
                try:
                    completed_time = datetime.fromisoformat(completed_at)
                    if completed_time < cutoff:
                        self.repo.delete(task["id"])
                        removed_count += 1
                except ValueError:
                    pass

        # Clean up cancelled tasks from the in-memory set
        with self._lock:
            current_task_ids = {t["id"] for t in self.repo.list_all()}
            self._cancelled_tasks = self._cancelled_tasks.intersection(current_task_ids)

        if removed_count > 0:
            print(f"Cleaned up {removed_count} old tasks")

        return removed_count

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor gracefully.

        Args:
            wait: If True, wait for running tasks to complete
        """
        print("Shutting down task service...")
        self._executor.shutdown(wait=wait)
        print("Task service shutdown complete")


# Singleton instance
task_service = TaskService()
