"""
JSON Source Repository - File-based implementation.

Educational Note: Source metadata is stored in sources_index.json
within each project directory.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.utils.path_utils import get_sources_index_path
from app.repositories.sources.interface import SourceRepositoryInterface


class JsonSourceRepository(SourceRepositoryInterface):
    """JSON file-based implementation of source repository."""

    def _load_index(self, project_id: str) -> Dict[str, Any]:
        """Load the sources index for a project."""
        index_path = get_sources_index_path(project_id)

        if not index_path.exists():
            return {
                "sources": [],
                "last_updated": datetime.now().isoformat()
            }

        try:
            with open(index_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {
                "sources": [],
                "last_updated": datetime.now().isoformat()
            }

    def _save_index(self, project_id: str, index_data: Dict[str, Any]) -> None:
        """Save the sources index for a project."""
        index_path = get_sources_index_path(project_id)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        index_data["last_updated"] = datetime.now().isoformat()
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all sources for a project."""
        index = self._load_index(project_id)
        return sorted(
            index["sources"],
            key=lambda s: s.get("created_at", ""),
            reverse=True
        )

    def get_by_id(self, project_id: str, source_id: str) -> Optional[Dict[str, Any]]:
        """Get source metadata by ID."""
        index = self._load_index(project_id)
        for source in index["sources"]:
            if source["id"] == source_id:
                return source
        return None

    def create(self, project_id: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new source entry."""
        index = self._load_index(project_id)

        # Ensure required fields
        if "created_at" not in source_data:
            source_data["created_at"] = datetime.now().isoformat()
        if "updated_at" not in source_data:
            source_data["updated_at"] = datetime.now().isoformat()
        if "status" not in source_data:
            source_data["status"] = "uploaded"
        if "active" not in source_data:
            source_data["active"] = True

        index["sources"].append(source_data)
        self._save_index(project_id, index)
        return source_data

    def update(
        self,
        project_id: str,
        source_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update source metadata."""
        index = self._load_index(project_id)

        for i, source in enumerate(index["sources"]):
            if source["id"] == source_id:
                # Apply updates
                for key, value in updates.items():
                    if value is not None:
                        source[key] = value

                source["updated_at"] = datetime.now().isoformat()
                index["sources"][i] = source
                self._save_index(project_id, index)
                return source

        return None

    def delete(self, project_id: str, source_id: str) -> bool:
        """Delete a source entry."""
        index = self._load_index(project_id)
        original_count = len(index["sources"])

        index["sources"] = [s for s in index["sources"] if s["id"] != source_id]

        if len(index["sources"]) < original_count:
            self._save_index(project_id, index)
            return True
        return False

    def update_status(
        self,
        project_id: str,
        source_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update source processing status."""
        updates = {"status": status}
        if error_message:
            updates["error_message"] = error_message
        if status == "processing":
            updates["processing_started_at"] = datetime.now().isoformat()
        if status in ("ready", "error"):
            updates["processing_completed_at"] = datetime.now().isoformat()

        result = self.update(project_id, source_id, updates)
        return result is not None

    def update_embedding_info(
        self,
        project_id: str,
        source_id: str,
        embedding_info: Dict[str, Any]
    ) -> bool:
        """Update source embedding information."""
        result = self.update(project_id, source_id, {"embedding_info": embedding_info})
        return result is not None

    def update_summary_info(
        self,
        project_id: str,
        source_id: str,
        summary_info: Dict[str, Any]
    ) -> bool:
        """Update source summary information."""
        result = self.update(project_id, source_id, {"summary_info": summary_info})
        return result is not None

    def set_active(self, project_id: str, source_id: str, active: bool) -> bool:
        """Set source active status."""
        result = self.update(project_id, source_id, {"active": active})
        return result is not None

    def get_active_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all active sources."""
        sources = self.list_by_project(project_id)
        return [s for s in sources if s.get("active", True)]

    def get_ready_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all sources with status 'ready'."""
        sources = self.list_by_project(project_id)
        return [s for s in sources if s.get("status") == "ready"]
