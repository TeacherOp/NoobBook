"""
Supabase Message Repository - PostgreSQL-based implementation.

Educational Note: Messages are stored in a separate table with a
sequence_number for ordering. The content column is JSONB to handle
both string content and tool_use/tool_result arrays.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.messages.interface import MessageRepositoryInterface


class SupabaseMessageRepository(MessageRepositoryInterface):
    """Supabase/PostgreSQL implementation of message repository."""

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
        """Get the messages table reference."""
        return self.client.table("messages")

    def _get_next_sequence(self, chat_id: str) -> int:
        """Get the next sequence number for a chat."""
        result = self.table.select("sequence_number").eq(
            "chat_id", chat_id
        ).order("sequence_number", desc=True).limit(1).execute()

        if not result.data:
            return 1
        return result.data[0]["sequence_number"] + 1

    def _to_message_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to message format."""
        message = {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "timestamp": row["created_at"]
        }

        if row.get("model"):
            message["model"] = row["model"]
        if row.get("tokens"):
            message["tokens"] = row["tokens"]
        if row.get("is_error"):
            message["error"] = True

        return message

    def _build_tool_result_content(
        self,
        tool_use_id: str,
        result: str,
        is_error: bool = False
    ) -> List[Dict[str, Any]]:
        """Build tool_result content block."""
        return [{
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": result,
            "is_error": is_error
        }]

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def get_all(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a chat in order."""
        result = self.table.select("*").eq(
            "chat_id", chat_id
        ).order("sequence_number").execute()

        return [self._to_message_dict(row) for row in result.data]

    def get_for_api(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get messages formatted for Claude API."""
        result = self.table.select("role, content").eq(
            "chat_id", chat_id
        ).order("sequence_number").execute()

        return [{"role": row["role"], "content": row["content"]} for row in result.data]

    def add(
        self,
        chat_id: str,
        role: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a message to a chat."""
        message_id = str(uuid.uuid4())
        sequence = self._get_next_sequence(chat_id)

        data = {
            "id": message_id,
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "sequence_number": sequence
        }

        if metadata:
            if "model" in metadata:
                data["model"] = metadata["model"]
            if "tokens" in metadata:
                data["tokens"] = metadata["tokens"]
            if metadata.get("error"):
                data["is_error"] = True

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to add message")

        return self._to_message_dict(result.data[0])

    def add_user_message(self, chat_id: str, content: str) -> Dict[str, Any]:
        """Add a user message."""
        return self.add(chat_id, "user", content)

    def add_assistant_message(
        self,
        chat_id: str,
        content: str,
        model: Optional[str] = None,
        tokens: Optional[Dict[str, int]] = None,
        error: bool = False
    ) -> Dict[str, Any]:
        """Add an assistant message."""
        metadata = {}
        if model:
            metadata["model"] = model
        if tokens:
            metadata["tokens"] = tokens
        if error:
            metadata["error"] = True

        return self.add(chat_id, "assistant", content, metadata if metadata else None)

    def add_tool_result(
        self,
        chat_id: str,
        tool_use_id: str,
        result: Any,
        is_error: bool = False
    ) -> Dict[str, Any]:
        """Add a tool result message."""
        content = self._build_tool_result_content(
            tool_use_id,
            str(result) if not isinstance(result, str) else result,
            is_error
        )
        return self.add(chat_id, "user", content)

    def get_message_count(self, chat_id: str) -> int:
        """Get message count."""
        result = self.table.select("id", count="exact").eq("chat_id", chat_id).execute()
        return result.count if result.count else 0

    def delete_chat_messages(self, chat_id: str) -> int:
        """Delete all messages for a chat."""
        # Get count first
        count = self.get_message_count(chat_id)

        # Delete messages
        self.table.delete().eq("chat_id", chat_id).execute()

        return count
