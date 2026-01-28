"""
Source Repository Interface - Contract for source data access.

Educational Note: Sources represent documents/files uploaded to a project.
The processing pipeline status flows: uploaded -> processing -> [embedding] -> ready
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class SourceRepositoryInterface(ABC):
    """Interface for source repository operations."""

    @abstractmethod
    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all sources for a project.

        Args:
            project_id: The project UUID

        Returns:
            List of source metadata, sorted by created_at (newest first)
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, project_id: str, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get source metadata by ID.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Source metadata or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def create(self, project_id: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new source entry.

        Args:
            project_id: The project UUID
            source_data: Source metadata including name, source_type, etc.

        Returns:
            Created source metadata
        """
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        project_id: str,
        source_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update source metadata.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            updates: Fields to update

        Returns:
            Updated source metadata or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, project_id: str, source_id: str) -> bool:
        """
        Delete a source entry.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        project_id: str,
        source_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update source processing status.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            status: New status (uploaded, processing, embedding, ready, error)
            error_message: Optional error message if status is 'error'

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_embedding_info(
        self,
        project_id: str,
        source_id: str,
        embedding_info: Dict[str, Any]
    ) -> bool:
        """
        Update source embedding information.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            embedding_info: Embedding metadata (status, vector_count, namespace)

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_summary_info(
        self,
        project_id: str,
        source_id: str,
        summary_info: Dict[str, Any]
    ) -> bool:
        """
        Update source summary information.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            summary_info: Summary metadata (summary text, generated_at)

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def set_active(self, project_id: str, source_id: str, active: bool) -> bool:
        """
        Set source active status (for filtering in chat).

        Args:
            project_id: The project UUID
            source_id: The source UUID
            active: Whether source should be included in chat context

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_active_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all active sources for a project.

        Args:
            project_id: The project UUID

        Returns:
            List of active source metadata
        """
        raise NotImplementedError

    @abstractmethod
    def get_ready_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all sources with status 'ready'.

        Args:
            project_id: The project UUID

        Returns:
            List of ready source metadata
        """
        raise NotImplementedError
