"""
Project Repository Interface - Contract for project data access.

Educational Note: This interface defines all operations needed for
project management. Both JSON and Supabase implementations must
provide these methods with the same signatures.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class ProjectRepositoryInterface(ABC):
    """
    Interface for project repository operations.

    Methods match the current ProjectService API to ensure smooth migration.
    """

    @abstractmethod
    def list_all(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all projects, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by (for multi-user support)

        Returns:
            List of project metadata, sorted by last_accessed (newest first)
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full project data by ID.

        Args:
            project_id: The project UUID

        Returns:
            Full project data or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project metadata only (without full data).

        Args:
            project_id: The project UUID

        Returns:
            Project metadata or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def create(
        self,
        name: str,
        description: str = "",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional description
            user_id: Optional user ID (for multi-user support)

        Returns:
            Created project metadata

        Raises:
            ValueError: If project name already exists for user
        """
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update project metadata.

        Args:
            project_id: The project UUID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated project metadata or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, project_id: str) -> bool:
        """
        Delete a project and all associated data.

        Args:
            project_id: The project UUID

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_last_accessed(self, project_id: str) -> bool:
        """
        Update the project's last_accessed timestamp.

        Args:
            project_id: The project UUID

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_settings(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project settings.

        Args:
            project_id: The project UUID

        Returns:
            Project settings or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_settings(
        self,
        project_id: str,
        settings: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update project settings.

        Args:
            project_id: The project UUID
            settings: Settings to update/merge

        Returns:
            Updated settings or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_cost_tracking(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project cost tracking data.

        Args:
            project_id: The project UUID

        Returns:
            Cost tracking data or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def add_cost(
        self,
        project_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> Optional[Dict[str, Any]]:
        """
        Add cost to project tracking (atomic operation).

        Args:
            project_id: The project UUID
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Cost in USD

        Returns:
            Updated cost for the model or None if project not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_memory(self, project_id: str) -> Optional[str]:
        """
        Get project-specific memory.

        Args:
            project_id: The project UUID

        Returns:
            Project memory text or None
        """
        raise NotImplementedError

    @abstractmethod
    def update_memory(self, project_id: str, memory: str) -> bool:
        """
        Update project-specific memory.

        Args:
            project_id: The project UUID
            memory: New memory text

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def name_exists(self, name: str, user_id: Optional[str] = None, exclude_id: Optional[str] = None) -> bool:
        """
        Check if a project name already exists.

        Args:
            name: Project name to check
            user_id: Optional user ID to scope the check
            exclude_id: Optional project ID to exclude from check (for updates)

        Returns:
            True if name exists, False otherwise
        """
        raise NotImplementedError
