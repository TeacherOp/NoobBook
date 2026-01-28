"""
JSON Project Repository - File-based implementation.

Educational Note: This wraps the existing JSON file storage logic,
providing the same interface as the Supabase implementation.
This allows gradual migration while keeping the JSON code working.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import Config
from app.repositories.projects.interface import ProjectRepositoryInterface


class JsonProjectRepository(ProjectRepositoryInterface):
    """
    JSON file-based implementation of project repository.

    This implementation maintains compatibility with the existing
    data structure in data/projects/.
    """

    def __init__(self):
        """Initialize with projects directory from config."""
        self.projects_dir = Config.PROJECTS_DIR
        self.projects_dir.mkdir(exist_ok=True, parents=True)
        self.index_file = self.projects_dir / "projects_index.json"
        self._initialize_index()

    def _initialize_index(self) -> None:
        """Initialize the projects index file if it doesn't exist."""
        if not self.index_file.exists():
            initial_index = {
                "projects": [],
                "last_updated": datetime.now().isoformat()
            }
            self._save_index(initial_index)

    def _load_index(self) -> Dict[str, Any]:
        """Load the projects index from file."""
        try:
            with open(self.index_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._initialize_index()
            with open(self.index_file, 'r') as f:
                return json.load(f)

    def _save_index(self, index_data: Dict[str, Any]) -> None:
        """Save the projects index to file."""
        index_data["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, 'w') as f:
            json.dump(index_data, f, indent=2)

    def _get_project_file(self, project_id: str) -> Path:
        """Get the path to a project's JSON file."""
        return self.projects_dir / f"{project_id}.json"

    def _load_project_data(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Load full project data from file."""
        project_file = self._get_project_file(project_id)
        if not project_file.exists():
            return None
        try:
            with open(project_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None

    def _save_project_data(self, project_id: str, data: Dict[str, Any]) -> None:
        """Save project data to file."""
        project_file = self._get_project_file(project_id)
        with open(project_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _update_index_entry(self, project_id: str, project_data: Dict[str, Any]) -> None:
        """Update a project entry in the index."""
        index = self._load_index()
        for i, project in enumerate(index["projects"]):
            if project["id"] == project_id:
                index["projects"][i] = {
                    "id": project_data["id"],
                    "name": project_data["name"],
                    "description": project_data.get("description", ""),
                    "created_at": project_data["created_at"],
                    "updated_at": project_data["updated_at"],
                    "last_accessed": project_data.get("last_accessed", project_data["updated_at"])
                }
                break
        self._save_index(index)

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def list_all(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all projects sorted by last_accessed."""
        index = self._load_index()
        projects = sorted(
            index["projects"],
            key=lambda p: p.get("last_accessed", p["created_at"]),
            reverse=True
        )
        return projects

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get full project data by ID."""
        return self._load_project_data(project_id)

    def get_metadata(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project metadata from index."""
        index = self._load_index()
        for project in index["projects"]:
            if project["id"] == project_id:
                return project
        return None

    def create(
        self,
        name: str,
        description: str = "",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new project."""
        if self.name_exists(name, user_id):
            raise ValueError(f"Project with name '{name}' already exists")

        project_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        project_metadata = {
            "id": project_id,
            "name": name,
            "description": description,
            "created_at": timestamp,
            "updated_at": timestamp,
            "last_accessed": timestamp
        }

        project_data = {
            **project_metadata,
            "documents": [],
            "notes": [],
            "meetings": [],
            "settings": {
                "ai_model": "claude-sonnet-4-5",
                "auto_save": True,
                "custom_prompt": None
            }
        }

        # Save project file
        self._save_project_data(project_id, project_data)

        # Update index
        index = self._load_index()
        index["projects"].append(project_metadata)
        self._save_index(index)

        print(f"Created project: {name} (ID: {project_id})")
        return project_metadata

    def update(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update project metadata."""
        project_data = self._load_project_data(project_id)
        if not project_data:
            return None

        if name and name != project_data["name"]:
            if self.name_exists(name, exclude_id=project_id):
                raise ValueError(f"Project with name '{name}' already exists")
            project_data["name"] = name

        if description is not None:
            project_data["description"] = description

        project_data["updated_at"] = datetime.now().isoformat()

        self._save_project_data(project_id, project_data)
        self._update_index_entry(project_id, project_data)

        return {
            "id": project_data["id"],
            "name": project_data["name"],
            "description": project_data["description"],
            "created_at": project_data["created_at"],
            "updated_at": project_data["updated_at"],
            "last_accessed": project_data["last_accessed"]
        }

    def delete(self, project_id: str) -> bool:
        """Delete a project."""
        project_file = self._get_project_file(project_id)
        if not project_file.exists():
            return False

        # Delete project file
        project_file.unlink()

        # Delete project directory if exists
        project_dir = self.projects_dir / project_id
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)

        # Remove from index
        index = self._load_index()
        index["projects"] = [p for p in index["projects"] if p["id"] != project_id]
        self._save_index(index)

        print(f"Deleted project: {project_id}")
        return True

    def update_last_accessed(self, project_id: str) -> bool:
        """Update last_accessed timestamp."""
        project_data = self._load_project_data(project_id)
        if not project_data:
            return False

        project_data["last_accessed"] = datetime.now().isoformat()
        self._save_project_data(project_id, project_data)
        self._update_index_entry(project_id, project_data)
        return True

    def get_settings(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project settings."""
        project_data = self._load_project_data(project_id)
        if not project_data:
            return None

        default_settings = {
            "ai_model": "claude-sonnet-4-5",
            "auto_save": True,
            "custom_prompt": None
        }
        return {**default_settings, **project_data.get("settings", {})}

    def update_settings(
        self,
        project_id: str,
        settings: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update project settings."""
        project_data = self._load_project_data(project_id)
        if not project_data:
            return None

        if "settings" not in project_data:
            project_data["settings"] = {
                "ai_model": "claude-sonnet-4-5",
                "auto_save": True,
                "custom_prompt": None
            }

        project_data["settings"].update(settings)
        project_data["updated_at"] = datetime.now().isoformat()

        self._save_project_data(project_id, project_data)
        return project_data["settings"]

    def get_cost_tracking(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project cost tracking."""
        project_data = self._load_project_data(project_id)
        if not project_data:
            return None
        return project_data.get("cost_tracking", {})

    def add_cost(
        self,
        project_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> Optional[Dict[str, Any]]:
        """Add cost to project tracking."""
        project_data = self._load_project_data(project_id)
        if not project_data:
            return None

        if "cost_tracking" not in project_data:
            project_data["cost_tracking"] = {}

        if model not in project_data["cost_tracking"]:
            project_data["cost_tracking"][model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0
            }

        project_data["cost_tracking"][model]["input_tokens"] += input_tokens
        project_data["cost_tracking"][model]["output_tokens"] += output_tokens
        project_data["cost_tracking"][model]["cost_usd"] += cost_usd

        self._save_project_data(project_id, project_data)
        return project_data["cost_tracking"][model]

    def get_memory(self, project_id: str) -> Optional[str]:
        """Get project memory."""
        # Project memory is stored separately
        memory_file = self.projects_dir / project_id / "memory.json"
        if not memory_file.exists():
            return None
        try:
            with open(memory_file, 'r') as f:
                data = json.load(f)
                return data.get("memory", "")
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def update_memory(self, project_id: str, memory: str) -> bool:
        """Update project memory."""
        project_dir = self.projects_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        memory_file = project_dir / "memory.json"
        data = {
            "memory": memory,
            "updated_at": datetime.now().isoformat()
        }
        with open(memory_file, 'w') as f:
            json.dump(data, f, indent=2)
        return True

    def name_exists(
        self,
        name: str,
        user_id: Optional[str] = None,
        exclude_id: Optional[str] = None
    ) -> bool:
        """Check if project name exists."""
        index = self._load_index()
        for project in index["projects"]:
            if project["name"].lower() == name.lower():
                if exclude_id and project["id"] == exclude_id:
                    continue
                return True
        return False
