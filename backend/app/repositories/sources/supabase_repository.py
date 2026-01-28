"""
Supabase Source Repository - PostgreSQL-based implementation.

Educational Note: Sources are stored in the sources table with JSONB
fields for flexible metadata storage (embedding_info, summary_info).
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.sources.interface import SourceRepositoryInterface


class SupabaseSourceRepository(SourceRepositoryInterface):
    """Supabase/PostgreSQL implementation of source repository."""

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
        """Get the sources table reference."""
        return self.client.table("sources")

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all sources for a project."""
        result = self.table.select("*").eq(
            "project_id", project_id
        ).order("created_at", desc=True).execute()

        return result.data

    def get_by_id(self, project_id: str, source_id: str) -> Optional[Dict[str, Any]]:
        """Get source metadata by ID."""
        result = self.table.select("*").eq("id", source_id).eq("project_id", project_id).execute()

        if not result.data:
            return None
        return result.data[0]

    def create(self, project_id: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new source entry."""
        now = datetime.now().isoformat()

        data = {
            **source_data,
            "project_id": project_id,
            "status": source_data.get("status", "uploaded"),
            "active": source_data.get("active", True),
            "created_at": source_data.get("created_at", now),
            "updated_at": now
        }

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create source")

        return result.data[0]

    def update(
        self,
        project_id: str,
        source_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update source metadata."""
        # Filter out None values
        filtered_updates = {k: v for k, v in updates.items() if v is not None}

        if not filtered_updates:
            return self.get_by_id(project_id, source_id)

        result = self.table.update(filtered_updates).eq("id", source_id).eq("project_id", project_id).execute()

        if not result.data:
            return None
        return result.data[0]

    def delete(self, project_id: str, source_id: str) -> bool:
        """Delete a source entry (chunks cascade automatically)."""
        result = self.table.delete().eq("id", source_id).eq("project_id", project_id).execute()
        return len(result.data) > 0 if result.data else False

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

        result = self.table.update(updates).eq("id", source_id).eq("project_id", project_id).execute()
        return len(result.data) > 0 if result.data else False

    def update_embedding_info(
        self,
        project_id: str,
        source_id: str,
        embedding_info: Dict[str, Any]
    ) -> bool:
        """Update source embedding information."""
        result = self.table.update({
            "embedding_info": embedding_info
        }).eq("id", source_id).eq("project_id", project_id).execute()

        return len(result.data) > 0 if result.data else False

    def update_summary_info(
        self,
        project_id: str,
        source_id: str,
        summary_info: Dict[str, Any]
    ) -> bool:
        """Update source summary information."""
        result = self.table.update({
            "summary_info": summary_info
        }).eq("id", source_id).eq("project_id", project_id).execute()

        return len(result.data) > 0 if result.data else False

    def set_active(self, project_id: str, source_id: str, active: bool) -> bool:
        """Set source active status."""
        result = self.table.update({
            "active": active
        }).eq("id", source_id).eq("project_id", project_id).execute()

        return len(result.data) > 0 if result.data else False

    def get_active_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all active sources."""
        result = self.table.select("*").eq(
            "project_id", project_id
        ).eq("active", True).order("created_at", desc=True).execute()

        return result.data

    def get_ready_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all sources with status 'ready'."""
        result = self.table.select("*").eq(
            "project_id", project_id
        ).eq("status", "ready").order("created_at", desc=True).execute()

        return result.data
