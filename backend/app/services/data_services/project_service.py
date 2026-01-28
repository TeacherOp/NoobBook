"""
Project Service - Business logic for project management.

Educational Note: This service layer handles all project-related operations,
keeping business logic separate from API endpoints and data access.
Data access is delegated to the repository layer, which handles the
actual storage (JSON files or Supabase).
"""
from datetime import datetime
from typing import Optional, Dict, List, Any

from app.repositories import get_project_repository


class ProjectService:
    """
    Service class for managing projects.

    Educational Note: This service uses the repository pattern for data access.
    Business logic stays here, while storage details are handled by repositories.
    """

    def __init__(self):
        """Initialize the project service with repository."""
        self._repo = None

    @property
    def repo(self):
        """Lazy-load the repository."""
        if self._repo is None:
            self._repo = get_project_repository()
        return self._repo

    def list_all_projects(self) -> List[Dict[str, Any]]:
        """
        List all available projects.

        Returns:
            List of project metadata (not full project data)

        Educational Note: We only return metadata to keep responses small.
        Full project data is loaded only when needed.
        """
        projects = self.repo.list_all()
        # Sort by last accessed time, most recent first
        return sorted(
            projects,
            key=lambda p: p.get("last_accessed", p.get("created_at", "")),
            reverse=True
        )

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description

        Returns:
            Created project object

        Raises:
            ValueError: If project name already exists

        Educational Note: We use UUID for project IDs to ensure uniqueness
        without needing a database sequence.
        """
        # Check if project name already exists
        existing = self.repo.list_all()
        if any(p["name"].lower() == name.lower() for p in existing):
            raise ValueError(f"Project with name '{name}' already exists")

        # Create project via repository
        project = self.repo.create(name=name, description=description)

        print(f"Created project: {name} (ID: {project['id']})")
        return project

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full project data by ID.

        Args:
            project_id: The project UUID

        Returns:
            Full project data or None if not found

        Educational Note: This loads the entire project data, which could
        be large. In production, you might want to load parts selectively.
        """
        project = self.repo.get_by_id(project_id)

        if project:
            # Update last accessed time
            self.repo.update(project_id, {
                "last_accessed": datetime.now().isoformat()
            })

        return project

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update project metadata.

        Args:
            project_id: The project UUID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated project metadata or None if not found

        Educational Note: We validate name uniqueness before updating.
        """
        # Get current project
        project = self.repo.get_by_id(project_id)
        if not project:
            return None

        # Check if new name conflicts with existing project
        if name and name != project["name"]:
            existing = self.repo.list_all()
            if any(p["name"].lower() == name.lower() for p in existing
                   if p["id"] != project_id):
                raise ValueError(f"Project with name '{name}' already exists")

        # Build updates
        updates = {}
        if name:
            updates["name"] = name
        if description is not None:  # Allow empty string to clear description
            updates["description"] = description

        if not updates:
            return project

        # Update via repository
        updated = self.repo.update(project_id, updates)
        if updated:
            print(f"Updated project: {project_id}")

        return updated

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            project_id: The project UUID

        Returns:
            True if deleted, False if not found

        Educational Note: We do a hard delete here for simplicity.
        In production, you might want soft delete (mark as deleted but keep data).
        """
        deleted = self.repo.delete(project_id)
        if deleted:
            print(f"Deleted project: {project_id}")
        return deleted

    def open_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Open a project (update last accessed time).

        Args:
            project_id: The project UUID

        Returns:
            Project metadata or None if not found

        Educational Note: This is similar to get_project but returns
        only metadata for efficiency when just marking as opened.
        """
        project = self.get_project(project_id)
        if not project:
            return None

        # Return only metadata
        return {
            "id": project["id"],
            "name": project["name"],
            "description": project.get("description", ""),
            "created_at": project["created_at"],
            "updated_at": project.get("updated_at", project["created_at"]),
            "last_accessed": project.get("last_accessed", project["created_at"])
        }

    def update_custom_prompt(
        self,
        project_id: str,
        custom_prompt: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Update the project's custom system prompt.

        Args:
            project_id: The project UUID
            custom_prompt: The custom prompt string, or None to reset to default

        Returns:
            Updated project settings or None if project not found

        Educational Note: Custom prompts allow users to customize how the AI
        behaves for specific projects. Setting to None reverts to the default prompt.
        """
        project = self.repo.get_by_id(project_id)
        if not project:
            return None

        # Ensure settings dict exists
        settings = project.get("settings", {
            "ai_model": "claude-sonnet-4-5",
            "auto_save": True,
            "custom_prompt": None
        })

        # Update the custom prompt (None means use default)
        settings["custom_prompt"] = custom_prompt

        # Update via repository
        self.repo.update(project_id, {"settings": settings})

        print(f"Updated custom prompt for project: {project_id}")
        return settings

    def get_project_settings(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the project's settings.

        Args:
            project_id: The project UUID

        Returns:
            Project settings or None if project not found
        """
        project = self.repo.get_by_id(project_id)
        if not project:
            return None

        # Return settings with defaults for any missing fields
        default_settings = {
            "ai_model": "claude-sonnet-4-5",
            "auto_save": True,
            "custom_prompt": None
        }

        settings = project.get("settings", {})
        # Merge with defaults
        return {**default_settings, **settings}


# Singleton instance
project_service = ProjectService()
