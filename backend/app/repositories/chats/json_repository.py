"""
JSON Chat Repository - File-based implementation.

Educational Note: This wraps the existing JSON file storage logic
for chat entities. Chats are stored in data/projects/{project_id}/chats/.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import Config
from app.repositories.chats.interface import ChatRepositoryInterface


class JsonChatRepository(ChatRepositoryInterface):
    """JSON file-based implementation of chat repository."""

    def __init__(self):
        """Initialize with projects directory from config."""
        self.projects_dir = Config.PROJECTS_DIR

    def _get_chats_dir(self, project_id: str) -> Path:
        """Get the chats directory for a project."""
        chats_dir = self.projects_dir / project_id / "chats"
        chats_dir.mkdir(exist_ok=True, parents=True)
        return chats_dir

    def _get_index_file(self, project_id: str) -> Path:
        """Get the chats index file path."""
        return self._get_chats_dir(project_id) / "chats_index.json"

    def _get_chat_file(self, project_id: str, chat_id: str) -> Path:
        """Get a specific chat's file path."""
        return self._get_chats_dir(project_id) / f"{chat_id}.json"

    def _load_index(self, project_id: str) -> Dict[str, Any]:
        """Load the chats index for a project."""
        index_file = self._get_index_file(project_id)

        if not index_file.exists():
            initial_index = {
                "project_id": project_id,
                "chats": [],
                "last_updated": datetime.now().isoformat()
            }
            self._save_index(project_id, initial_index)
            return initial_index

        try:
            with open(index_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            initial_index = {
                "project_id": project_id,
                "chats": [],
                "last_updated": datetime.now().isoformat()
            }
            self._save_index(project_id, initial_index)
            return initial_index

    def _save_index(self, project_id: str, index_data: Dict[str, Any]) -> bool:
        """Save the chats index."""
        index_data["last_updated"] = datetime.now().isoformat()
        index_file = self._get_index_file(project_id)

        try:
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
            return True
        except IOError:
            return False

    def _load_chat_file(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Load chat data from file."""
        chat_file = self._get_chat_file(project_id, chat_id)
        if not chat_file.exists():
            return None
        try:
            with open(chat_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None

    def _save_chat_file(self, project_id: str, chat_id: str, data: Dict[str, Any]) -> bool:
        """Save chat data to file."""
        chat_file = self._get_chat_file(project_id, chat_id)
        try:
            with open(chat_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except IOError:
            return False

    def _update_index_entry(
        self,
        project_id: str,
        chat_id: str,
        chat_data: Dict[str, Any]
    ) -> None:
        """Update a chat's entry in the index."""
        index = self._load_index(project_id)

        for i, chat in enumerate(index["chats"]):
            if chat["id"] == chat_id:
                index["chats"][i] = {
                    "id": chat_data["id"],
                    "title": chat_data["title"],
                    "created_at": chat_data["created_at"],
                    "updated_at": chat_data["updated_at"],
                    "message_count": len(chat_data.get("messages", []))
                }
                break

        self._save_index(project_id, index)

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all chats for a project."""
        index = self._load_index(project_id)
        chats = sorted(
            index["chats"],
            key=lambda c: c.get("updated_at", c["created_at"]),
            reverse=True
        )
        return chats

    def get_by_id(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get full chat data (without messages for display)."""
        chat_data = self._load_chat_file(project_id, chat_id)
        if not chat_data:
            return None

        # Filter out tool_use/tool_result messages for display
        chat_data["messages"] = [
            msg for msg in chat_data.get("messages", [])
            if isinstance(msg.get("content"), str)
        ]

        # Ensure studio_signals exists
        if "studio_signals" not in chat_data:
            chat_data["studio_signals"] = []

        return chat_data

    def get_metadata(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat metadata only."""
        index = self._load_index(project_id)
        for chat in index["chats"]:
            if chat["id"] == chat_id:
                return chat
        return None

    def create(self, project_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """Create a new chat."""
        chat_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        chat_metadata = {
            "id": chat_id,
            "title": title,
            "created_at": timestamp,
            "updated_at": timestamp,
            "message_count": 0
        }

        chat_data = {
            "id": chat_id,
            "project_id": project_id,
            "title": title,
            "created_at": timestamp,
            "updated_at": timestamp,
            "messages": [],
            "metadata": {
                "source_references": [],
                "sub_agents": []
            },
            "studio_signals": [],
            "message_count": 0
        }

        # Save chat file
        self._save_chat_file(project_id, chat_id, chat_data)

        # Update index
        index = self._load_index(project_id)
        index["chats"].append(chat_metadata)
        self._save_index(project_id, index)

        print(f"Created chat: {title} (ID: {chat_id})")
        return chat_metadata

    def update(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update chat metadata."""
        chat_data = self._load_chat_file(project_id, chat_id)
        if not chat_data:
            return None

        # Apply allowed updates
        allowed_fields = ["title", "metadata", "studio_signals"]
        for key, value in updates.items():
            if key in allowed_fields:
                chat_data[key] = value

        chat_data["updated_at"] = datetime.now().isoformat()

        # Save chat file
        self._save_chat_file(project_id, chat_id, chat_data)

        # Update index
        self._update_index_entry(project_id, chat_id, chat_data)

        return {
            "id": chat_data["id"],
            "title": chat_data["title"],
            "created_at": chat_data["created_at"],
            "updated_at": chat_data["updated_at"],
            "message_count": len(chat_data.get("messages", []))
        }

    def delete(self, project_id: str, chat_id: str) -> bool:
        """Delete a chat."""
        chat_file = self._get_chat_file(project_id, chat_id)
        if not chat_file.exists():
            return False

        # Delete chat file
        chat_file.unlink()

        # Remove from index
        index = self._load_index(project_id)
        index["chats"] = [c for c in index["chats"] if c["id"] != chat_id]
        self._save_index(project_id, index)

        print(f"Deleted chat: {chat_id}")
        return True

    def update_message_count(self, project_id: str, chat_id: str, count: int) -> bool:
        """Update message count."""
        chat_data = self._load_chat_file(project_id, chat_id)
        if not chat_data:
            return False

        chat_data["message_count"] = count
        self._save_chat_file(project_id, chat_id, chat_data)
        self._update_index_entry(project_id, chat_id, chat_data)
        return True

    def get_studio_signals(self, project_id: str, chat_id: str) -> List[Dict[str, Any]]:
        """Get studio signals."""
        chat_data = self._load_chat_file(project_id, chat_id)
        if not chat_data:
            return []
        return chat_data.get("studio_signals", [])

    def update_studio_signals(
        self,
        project_id: str,
        chat_id: str,
        signals: List[Dict[str, Any]]
    ) -> bool:
        """Update studio signals."""
        chat_data = self._load_chat_file(project_id, chat_id)
        if not chat_data:
            return False

        chat_data["studio_signals"] = signals
        chat_data["updated_at"] = datetime.now().isoformat()
        self._save_chat_file(project_id, chat_id, chat_data)
        return True
