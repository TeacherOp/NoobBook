"""
JSON Message Repository - File-based implementation.

Educational Note: Messages are stored embedded in chat JSON files.
This implementation loads/saves the chat file for each operation.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import Config
from app.repositories.messages.interface import MessageRepositoryInterface


class JsonMessageRepository(MessageRepositoryInterface):
    """JSON file-based implementation of message repository."""

    def __init__(self):
        """Initialize with projects directory from config."""
        self.projects_dir = Config.PROJECTS_DIR

    def _get_chat_file_from_id(self, chat_id: str) -> Optional[Path]:
        """
        Find the chat file by searching project directories.

        Educational Note: Since messages don't store project_id in JSON,
        we need to search for the chat file. This is inefficient but
        maintains backward compatibility.
        """
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                chat_file = project_dir / "chats" / f"{chat_id}.json"
                if chat_file.exists():
                    return chat_file
        return None

    def _load_chat_data(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Load chat data from file."""
        chat_file = self._get_chat_file_from_id(chat_id)
        if not chat_file:
            return None
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def _save_chat_data(self, chat_id: str, data: Dict[str, Any]) -> bool:
        """Save chat data to file."""
        chat_file = self._get_chat_file_from_id(chat_id)
        if not chat_file:
            return False
        try:
            with open(chat_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except IOError:
            return False

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
        """Get all messages for a chat."""
        chat_data = self._load_chat_data(chat_id)
        if not chat_data:
            return []
        return chat_data.get("messages", [])

    def get_for_api(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get messages formatted for Claude API."""
        messages = self.get_all(chat_id)
        return [{"role": msg["role"], "content": msg["content"]} for msg in messages]

    def add(
        self,
        chat_id: str,
        role: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a message to a chat."""
        chat_data = self._load_chat_data(chat_id)
        if not chat_data:
            raise ValueError(f"Chat {chat_id} not found")

        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }

        if metadata:
            message.update(metadata)

        chat_data["messages"].append(message)
        chat_data["updated_at"] = datetime.now().isoformat()
        chat_data["message_count"] = len(chat_data["messages"])

        self._save_chat_data(chat_id, chat_data)
        return message

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
        messages = self.get_all(chat_id)
        return len(messages)

    def delete_chat_messages(self, chat_id: str) -> int:
        """Delete all messages for a chat."""
        chat_data = self._load_chat_data(chat_id)
        if not chat_data:
            return 0

        count = len(chat_data.get("messages", []))
        chat_data["messages"] = []
        chat_data["message_count"] = 0
        chat_data["updated_at"] = datetime.now().isoformat()

        self._save_chat_data(chat_id, chat_data)
        return count
