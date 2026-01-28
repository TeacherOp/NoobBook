"""
Chat Service - CRUD operations for chat entities.

Educational Note: This service manages chat entity lifecycle within projects.
It handles creating, listing, getting, updating, and deleting chats.
Data access is delegated to the repository layer.

Separation of Concerns:
- chat_service.py: Chat CRUD (this file)
- claude_service.py: Claude API interactions
- message_service.py: Message persistence
- prompt_loader.py: Prompt management
"""
from typing import Optional, Dict, List, Any

from app.repositories import get_chat_repository


class ChatService:
    """
    Service class for chat entity management.

    Educational Note: A chat is a conversation container within a project.
    It has metadata (title, timestamps) and holds messages.
    Data access is handled by the repository layer.
    """

    def __init__(self):
        """Initialize the chat service."""
        self._repo = None

    @property
    def repo(self):
        """Lazy-load the repository."""
        if self._repo is None:
            self._repo = get_chat_repository()
        return self._repo

    def list_chats(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all chats for a project.

        Educational Note: Returns metadata only (not full messages) for
        efficient loading of chat lists in the UI.

        Args:
            project_id: The project UUID

        Returns:
            List of chat metadata, sorted by most recent first
        """
        chats = self.repo.list_by_project(project_id)

        # Sort by updated_at, most recent first
        return sorted(
            chats,
            key=lambda c: c.get("updated_at", c.get("created_at", "")),
            reverse=True
        )

    def create_chat(self, project_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """
        Create a new chat in a project.

        Educational Note: Initializes an empty conversation with metadata.
        Messages are added separately via message_service.

        Args:
            project_id: The project UUID
            title: Initial chat title

        Returns:
            Created chat metadata
        """
        chat = self.repo.create(project_id=project_id, title=title)
        print(f"Created chat: {title} (ID: {chat['id']})")
        return chat

    def get_chat(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full chat data including messages and studio signals.

        Educational Note: Filters out tool_use and tool_result messages
        from the response. These are internal messages used in the tool
        chain and shouldn't be displayed to users. Studio signals are
        included as-is for frontend to render active studio items.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Full chat data or None if not found
        """
        chat_data = self.repo.get_by_id(project_id, chat_id)

        if not chat_data:
            return None

        # Filter out tool_use and tool_result messages for display
        # These have content as arrays instead of strings
        if "messages" in chat_data:
            chat_data["messages"] = [
                msg for msg in chat_data.get("messages", [])
                if isinstance(msg.get("content"), str)
            ]

        # Ensure studio_signals exists (even if empty)
        if "studio_signals" not in chat_data:
            chat_data["studio_signals"] = []

        return chat_data

    def get_chat_metadata(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chat metadata only (without messages).

        Educational Note: Useful for quick lookups without loading
        the full message history.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Chat metadata or None if not found
        """
        return self.repo.get_metadata(project_id, chat_id)

    def update_chat(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update chat metadata.

        Educational Note: Currently supports updating title.
        Messages are updated via message_service.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            updates: Dict of fields to update (e.g., {"title": "New Title"})

        Returns:
            Updated chat metadata or None if not found
        """
        # Filter to allowed updates only
        allowed_updates = {k: v for k, v in updates.items() if k in ["title"]}

        if not allowed_updates:
            return self.get_chat_metadata(project_id, chat_id)

        updated = self.repo.update(project_id, chat_id, allowed_updates)
        return updated

    def delete_chat(self, project_id: str, chat_id: str) -> bool:
        """
        Delete a chat and all its messages.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if deleted, False if not found
        """
        deleted = self.repo.delete(project_id, chat_id)
        if deleted:
            print(f"Deleted chat: {chat_id}")
        return deleted

    def sync_chat_to_index(self, project_id: str, chat_id: str) -> bool:
        """
        Sync a chat's metadata to the index.

        Educational Note: Called after message_service adds messages
        to ensure the index stays up to date.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if successful
        """
        # The repository handles this internally
        # This method exists for backward compatibility
        chat_data = self.repo.get_by_id(project_id, chat_id)
        return chat_data is not None


# Singleton instance for easy import
chat_service = ChatService()
