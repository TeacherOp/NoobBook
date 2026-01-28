"""
Supabase Chat Repository - PostgreSQL-based implementation.

Educational Note: Chats are stored in the chats table. Messages are
stored separately in the messages table, linked by chat_id.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.chats.interface import ChatRepositoryInterface


class SupabaseChatRepository(ChatRepositoryInterface):
    """Supabase/PostgreSQL implementation of chat repository."""

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
        """Get the chats table reference."""
        return self.client.table("chats")

    def _to_metadata(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to chat metadata format."""
        return {
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row.get("message_count", 0)
        }

    def _to_full_chat(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to full chat format."""
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "message_count": row.get("message_count", 0),
            "metadata": row.get("metadata", {"source_references": [], "sub_agents": []}),
            "studio_signals": row.get("studio_signals", []),
            "messages": []  # Messages fetched separately
        }

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all chats for a project."""
        result = self.table.select(
            "id, title, created_at, updated_at, message_count"
        ).eq("project_id", project_id).order("updated_at", desc=True).execute()

        return [self._to_metadata(row) for row in result.data]

    def get_by_id(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get full chat data."""
        result = self.table.select("*").eq("id", chat_id).eq("project_id", project_id).execute()

        if not result.data:
            return None

        return self._to_full_chat(result.data[0])

    def get_metadata(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat metadata only."""
        result = self.table.select(
            "id, title, created_at, updated_at, message_count"
        ).eq("id", chat_id).eq("project_id", project_id).execute()

        if not result.data:
            return None

        return self._to_metadata(result.data[0])

    def create(self, project_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """Create a new chat."""
        chat_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        data = {
            "id": chat_id,
            "project_id": project_id,
            "title": title,
            "message_count": 0,
            "metadata": {"source_references": [], "sub_agents": []},
            "studio_signals": [],
            "created_at": now,
            "updated_at": now
        }

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create chat")

        print(f"Created chat: {title} (ID: {chat_id})")
        return self._to_metadata(result.data[0])

    def update(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update chat metadata."""
        # Filter to allowed fields
        allowed_fields = ["title", "metadata", "studio_signals"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return self.get_metadata(project_id, chat_id)

        result = self.table.update(filtered_updates).eq("id", chat_id).eq("project_id", project_id).execute()

        if not result.data:
            return None

        return self._to_metadata(result.data[0])

    def delete(self, project_id: str, chat_id: str) -> bool:
        """Delete a chat (messages cascade automatically)."""
        result = self.table.delete().eq("id", chat_id).eq("project_id", project_id).execute()
        deleted = len(result.data) > 0 if result.data else False

        if deleted:
            print(f"Deleted chat: {chat_id}")

        return deleted

    def update_message_count(self, project_id: str, chat_id: str, count: int) -> bool:
        """
        Update message count.

        Educational Note: In Supabase, this is handled automatically by a trigger.
        This method exists for compatibility with the JSON implementation.
        """
        result = self.table.update({
            "message_count": count
        }).eq("id", chat_id).eq("project_id", project_id).execute()

        return len(result.data) > 0 if result.data else False

    def get_studio_signals(self, project_id: str, chat_id: str) -> List[Dict[str, Any]]:
        """Get studio signals."""
        result = self.table.select("studio_signals").eq("id", chat_id).eq("project_id", project_id).execute()

        if not result.data:
            return []

        return result.data[0].get("studio_signals", [])

    def update_studio_signals(
        self,
        project_id: str,
        chat_id: str,
        signals: List[Dict[str, Any]]
    ) -> bool:
        """Update studio signals."""
        result = self.table.update({
            "studio_signals": signals
        }).eq("id", chat_id).eq("project_id", project_id).execute()

        return len(result.data) > 0 if result.data else False
