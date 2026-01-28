"""
Supabase Studio Repository - PostgreSQL-based implementation.

Educational Note: All studio jobs are stored in a single studio_jobs table
with job_type as a column. This simplifies the schema while still allowing
type-specific queries. Config and output are JSONB for flexibility.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.studio.interface import StudioRepositoryInterface


class SupabaseStudioRepository(StudioRepositoryInterface):
    """Supabase/PostgreSQL implementation of studio repository."""

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
        """Get the studio_jobs table reference."""
        return self.client.table("studio_jobs")

    def _to_job_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to job format (matching JSON format)."""
        return {
            "id": row["id"],
            "status": row["status"],
            "config": row.get("config", {}),
            "output": row.get("output", {}),
            "output_paths": row.get("output_paths", {}),
            "error_message": row.get("error_message"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row.get("completed_at")
        }

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def create_job(
        self,
        project_id: str,
        job_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new studio job."""
        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        data = {
            "id": job_id,
            "project_id": project_id,
            "job_type": job_type,
            "status": "pending",
            "config": config or {},
            "output": {},
            "output_paths": {},
            "created_at": now,
            "updated_at": now
        }

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create studio job")

        return self._to_job_dict(result.data[0])

    def get_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get a job by ID and type."""
        result = self.table.select("*").eq("id", job_id).eq(
            "project_id", project_id
        ).eq("job_type", job_type).execute()

        if not result.data:
            return None
        return self._to_job_dict(result.data[0])

    def list_jobs(
        self,
        project_id: str,
        job_type: str
    ) -> List[Dict[str, Any]]:
        """List all jobs of a specific type."""
        result = self.table.select("*").eq(
            "project_id", project_id
        ).eq("job_type", job_type).order("created_at", desc=True).execute()

        return [self._to_job_dict(row) for row in result.data]

    def update_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a job."""
        # Filter out None values
        filtered_updates = {k: v for k, v in updates.items() if v is not None}

        if not filtered_updates:
            return self.get_job(project_id, job_id, job_type)

        result = self.table.update(filtered_updates).eq("id", job_id).eq(
            "project_id", project_id
        ).eq("job_type", job_type).execute()

        if not result.data:
            return None
        return self._to_job_dict(result.data[0])

    def delete_job(
        self,
        project_id: str,
        job_id: str,
        job_type: str
    ) -> bool:
        """Delete a job."""
        result = self.table.delete().eq("id", job_id).eq(
            "project_id", project_id
        ).eq("job_type", job_type).execute()

        return len(result.data) > 0 if result.data else False

    def update_job_status(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update job status."""
        updates = {"status": status}

        if error_message:
            updates["error_message"] = error_message
        if status == "ready":
            updates["completed_at"] = datetime.now().isoformat()

        result = self.table.update(updates).eq("id", job_id).eq(
            "project_id", project_id
        ).eq("job_type", job_type).execute()

        return len(result.data) > 0 if result.data else False

    def set_job_output(
        self,
        project_id: str,
        job_id: str,
        job_type: str,
        output: Dict[str, Any],
        output_paths: Optional[Dict[str, str]] = None
    ) -> bool:
        """Set job output data."""
        updates = {"output": output}
        if output_paths:
            updates["output_paths"] = output_paths

        result = self.table.update(updates).eq("id", job_id).eq(
            "project_id", project_id
        ).eq("job_type", job_type).execute()

        return len(result.data) > 0 if result.data else False
