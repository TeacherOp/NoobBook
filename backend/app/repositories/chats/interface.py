"""
Chat Repository Interface - Contract for chat data access.

Educational Note: Chats are conversation containers within projects.
This interface defines operations for managing chat lifecycle and metadata.
Messages are handled by a separate MessageRepository.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class ChatRepositoryInterface(ABC):
    """Interface for chat repository operations."""

    @abstractmethod
    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all chats for a project.

        Args:
            project_id: The project UUID

        Returns:
            List of chat metadata, sorted by updated_at (newest first)
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full chat data including metadata but without messages.

        Educational Note: Messages are retrieved separately via MessageRepository
        to allow pagination and efficient loading.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Chat data or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chat metadata only.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Chat metadata or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def create(self, project_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """
        Create a new chat in a project.

        Args:
            project_id: The project UUID
            title: Initial chat title

        Returns:
            Created chat metadata
        """
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update chat metadata.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            updates: Fields to update (title, metadata, studio_signals)

        Returns:
            Updated chat metadata or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, project_id: str, chat_id: str) -> bool:
        """
        Delete a chat and all its messages.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def update_message_count(self, project_id: str, chat_id: str, count: int) -> bool:
        """
        Update the denormalized message count.

        Educational Note: Message count is denormalized for efficient display.
        This is called after adding/removing messages.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            count: New message count

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_studio_signals(self, project_id: str, chat_id: str) -> List[Dict[str, Any]]:
        """
        Get studio signals for a chat.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            List of studio signals
        """
        raise NotImplementedError

    @abstractmethod
    def update_studio_signals(
        self,
        project_id: str,
        chat_id: str,
        signals: List[Dict[str, Any]]
    ) -> bool:
        """
        Update studio signals for a chat.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            signals: New studio signals list

        Returns:
            True if updated, False if not found
        """
        raise NotImplementedError
