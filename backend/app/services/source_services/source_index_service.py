"""
Source Index Service - CRUD operations for the sources index.

Educational Note: This service manages source metadata, which can be stored
in JSON files or Supabase depending on configuration. It delegates data access
to the repository layer.

The source structure:
{
    "id": "uuid",
    "name": "...",
    "status": "uploaded|processing|embedding|ready|error",
    ... other metadata
}
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.repositories import get_source_repository


# Cache the repository instance
_repo = None


def _get_repo():
    """Get or create the source repository singleton."""
    global _repo
    if _repo is None:
        _repo = get_source_repository()
    return _repo


def load_index(project_id: str) -> Dict[str, Any]:
    """
    Load the sources index for a project.

    Educational Note: Returns empty structure if no sources exist.
    This is safe to call for new projects.

    Args:
        project_id: The project UUID

    Returns:
        Dict with "sources" list and "last_updated" timestamp
    """
    sources = _get_repo().list_by_project(project_id)
    return {
        "sources": sources,
        "last_updated": datetime.now().isoformat()
    }


def save_index(project_id: str, index_data: Dict[str, Any]) -> None:
    """
    Save the sources index for a project.

    Educational Note: This is maintained for backward compatibility.
    The repository handles actual persistence.

    Args:
        project_id: The project UUID
        index_data: The index data to save (contains "sources" list)
    """
    # The repository handles individual source updates
    # This function exists for backward compatibility
    pass


def add_source_to_index(project_id: str, source_metadata: Dict[str, Any]) -> None:
    """
    Add a new source to the index.

    Args:
        project_id: The project UUID
        source_metadata: Complete source metadata dict
    """
    _get_repo().create(project_id, source_metadata)


def remove_source_from_index(project_id: str, source_id: str) -> bool:
    """
    Remove a source from the index.

    Args:
        project_id: The project UUID
        source_id: The source UUID to remove

    Returns:
        True if source was found and removed, False otherwise
    """
    return _get_repo().delete(project_id, source_id)


def get_source_from_index(project_id: str, source_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a source's metadata from the index.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        Source metadata dict or None if not found
    """
    return _get_repo().get_by_id(project_id, source_id)


def update_source_in_index(
    project_id: str,
    source_id: str,
    updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Update a source's metadata in the index.

    Educational Note: This is a generic update function. Pass a dict
    with the fields you want to update.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        updates: Dict of fields to update

    Returns:
        Updated source metadata or None if not found
    """
    return _get_repo().update(project_id, source_id, updates)


def list_sources_from_index(project_id: str) -> List[Dict[str, Any]]:
    """
    List all sources from the index, sorted by created_at (newest first).

    Args:
        project_id: The project UUID

    Returns:
        List of source metadata dicts
    """
    sources = _get_repo().list_by_project(project_id)
    return sorted(
        sources,
        key=lambda s: s.get("created_at", ""),
        reverse=True
    )
