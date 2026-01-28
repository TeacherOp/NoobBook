"""
Supabase Project Repository - PostgreSQL-based implementation.

Educational Note: This implementation uses Supabase's PostgREST API
for database operations. The Python client provides a fluent interface
for building queries that map to SQL operations.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.projects.interface import ProjectRepositoryInterface


# Default user ID for single-user mode
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


class SupabaseProjectRepository(ProjectRepositoryInterface):
    """
    Supabase/PostgreSQL implementation of project repository.

    Educational Note: Supabase PostgREST provides a REST API on top of
    PostgreSQL. The Python client translates method calls to HTTP requests:
    - .select() -> GET request
    - .insert() -> POST request
    - .update() -> PATCH request
    - .delete() -> DELETE request
    """

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
        """Get the projects table reference."""
        return self.client.table("projects")

    def _to_metadata(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert database row to project metadata format.

        Educational Note: This ensures the API response format matches
        what the existing services expect.
        """
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description", ""),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_accessed": row.get("last_accessed", row["updated_at"])
        }

    def _to_full_project(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to full project format."""
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description", ""),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_accessed": row.get("last_accessed", row["updated_at"]),
            "settings": row.get("settings", {
                "ai_model": "claude-sonnet-4-5",
                "auto_save": True,
                "custom_prompt": None
            }),
            "cost_tracking": row.get("cost_tracking", {}),
            "documents": [],  # Legacy fields for compatibility
            "notes": [],
            "meetings": []
        }

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def list_all(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all projects sorted by last_accessed."""
        query = self.table.select("id, name, description, created_at, updated_at, last_accessed")

        if user_id:
            query = query.eq("user_id", user_id)

        query = query.order("last_accessed", desc=True)

        result = query.execute()
        return [self._to_metadata(row) for row in result.data]

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get full project data by ID."""
        result = self.table.select("*").eq("id", project_id).execute()

        if not result.data:
            return None

        return self._to_full_project(result.data[0])

    def get_metadata(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project metadata only."""
        result = self.table.select(
            "id, name, description, created_at, updated_at, last_accessed"
        ).eq("id", project_id).execute()

        if not result.data:
            return None

        return self._to_metadata(result.data[0])

    def create(
        self,
        name: str,
        description: str = "",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new project."""
        # Use default user if not specified
        actual_user_id = user_id or DEFAULT_USER_ID

        if self.name_exists(name, actual_user_id):
            raise ValueError(f"Project with name '{name}' already exists")

        project_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        data = {
            "id": project_id,
            "user_id": actual_user_id,
            "name": name,
            "description": description,
            "settings": {
                "ai_model": "claude-sonnet-4-5",
                "auto_save": True,
                "custom_prompt": None
            },
            "cost_tracking": {},
            "created_at": now,
            "updated_at": now,
            "last_accessed": now
        }

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create project")

        print(f"Created project: {name} (ID: {project_id})")
        return self._to_metadata(result.data[0])

    def update(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update project metadata."""
        # Check if project exists
        existing = self.get_metadata(project_id)
        if not existing:
            return None

        updates = {}

        if name is not None and name != existing["name"]:
            if self.name_exists(name, exclude_id=project_id):
                raise ValueError(f"Project with name '{name}' already exists")
            updates["name"] = name

        if description is not None:
            updates["description"] = description

        if not updates:
            return existing

        result = self.table.update(updates).eq("id", project_id).execute()

        if not result.data:
            return None

        return self._to_metadata(result.data[0])

    def delete(self, project_id: str) -> bool:
        """Delete a project (cascades to related tables)."""
        result = self.table.delete().eq("id", project_id).execute()
        deleted = len(result.data) > 0 if result.data else False

        if deleted:
            print(f"Deleted project: {project_id}")

        return deleted

    def update_last_accessed(self, project_id: str) -> bool:
        """Update last_accessed timestamp."""
        result = self.table.update({
            "last_accessed": datetime.now().isoformat()
        }).eq("id", project_id).execute()

        return len(result.data) > 0 if result.data else False

    def get_settings(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project settings."""
        result = self.table.select("settings").eq("id", project_id).execute()

        if not result.data:
            return None

        default_settings = {
            "ai_model": "claude-sonnet-4-5",
            "auto_save": True,
            "custom_prompt": None
        }
        settings = result.data[0].get("settings", {})
        return {**default_settings, **settings}

    def update_settings(
        self,
        project_id: str,
        settings: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update project settings."""
        # Get current settings
        current = self.get_settings(project_id)
        if current is None:
            return None

        # Merge settings
        new_settings = {**current, **settings}

        result = self.table.update({
            "settings": new_settings
        }).eq("id", project_id).execute()

        if not result.data:
            return None

        return result.data[0].get("settings", new_settings)

    def get_cost_tracking(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project cost tracking."""
        result = self.table.select("cost_tracking").eq("id", project_id).execute()

        if not result.data:
            return None

        return result.data[0].get("cost_tracking", {})

    def add_cost(
        self,
        project_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> Optional[Dict[str, Any]]:
        """
        Add cost to project tracking using atomic PostgreSQL function.

        Educational Note: We use a PostgreSQL function for atomic updates
        to prevent race conditions when multiple requests update costs
        simultaneously.
        """
        try:
            result = self.client.rpc(
                "add_project_cost",
                {
                    "p_project_id": project_id,
                    "p_model": model,
                    "p_input_tokens": input_tokens,
                    "p_output_tokens": output_tokens,
                    "p_cost_usd": cost_usd
                }
            ).execute()

            return result.data if result.data else None
        except Exception as e:
            print(f"Error adding cost: {e}")
            # Fallback to non-atomic update
            return self._add_cost_fallback(
                project_id, model, input_tokens, output_tokens, cost_usd
            )

    def _add_cost_fallback(
        self,
        project_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> Optional[Dict[str, Any]]:
        """Non-atomic fallback for cost tracking."""
        current = self.get_cost_tracking(project_id)
        if current is None:
            return None

        if model not in current:
            current[model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0
            }

        current[model]["input_tokens"] += input_tokens
        current[model]["output_tokens"] += output_tokens
        current[model]["cost_usd"] += cost_usd

        self.table.update({"cost_tracking": current}).eq("id", project_id).execute()
        return current[model]

    def get_memory(self, project_id: str) -> Optional[str]:
        """Get project memory."""
        result = self.table.select("project_memory").eq("id", project_id).execute()

        if not result.data:
            return None

        return result.data[0].get("project_memory")

    def update_memory(self, project_id: str, memory: str) -> bool:
        """Update project memory."""
        result = self.table.update({
            "project_memory": memory
        }).eq("id", project_id).execute()

        return len(result.data) > 0 if result.data else False

    def name_exists(
        self,
        name: str,
        user_id: Optional[str] = None,
        exclude_id: Optional[str] = None
    ) -> bool:
        """Check if project name exists."""
        query = self.table.select("id").ilike("name", name)

        if user_id:
            query = query.eq("user_id", user_id)

        if exclude_id:
            query = query.neq("id", exclude_id)

        result = query.execute()
        return len(result.data) > 0
