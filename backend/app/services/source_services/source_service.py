"""
Source Service - Business logic for managing project sources.

Educational Note: This service provides the main interface for source operations.
It delegates to specialized modules for cleaner code organization:
- source_index_service: Index CRUD operations
- source_upload: Upload handling (file, URL, text)
- source_processing: Processing orchestration

CRUD Operations are kept here for backwards compatibility with API routes.
"""
from pathlib import Path
from typing import Optional, Dict, List, Any
from werkzeug.datastructures import FileStorage

from app.services.source_services import source_index_service
from app.services.source_services.source_upload import (
    upload_file,
    create_from_existing_file,
    upload_url,
    upload_text,
    upload_research,
    upload_database
)
from app.utils.path_utils import (
    get_raw_dir,
    get_processed_dir,
    get_chunks_dir
)
from app.utils.file_utils import ALLOWED_EXTENSIONS


class SourceService:
    """
    Service class for managing project sources.

    Educational Note: This is the main entry point for source operations.
    Most logic has been delegated to specialized modules, keeping this
    class focused on orchestrating the modules and providing a clean API.
    """

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def list_sources(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all sources for a project.

        Args:
            project_id: The project UUID

        Returns:
            List of source metadata dictionaries (newest first)
        """
        return source_index_service.list_sources_from_index(project_id)

    def get_source(self, project_id: str, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific source's metadata.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Source metadata or None if not found
        """
        return source_index_service.get_source_from_index(project_id, source_id)

    def get_source_file_path(self, project_id: str, source_id: str) -> Optional[Path]:
        """
        Get the file path for a source's raw file.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Path to the raw file or None if not found
        """
        source = self.get_source(project_id, source_id)
        if not source:
            return None

        file_path = get_raw_dir(project_id) / source["stored_filename"]
        if file_path.exists():
            return file_path

        return None

    def update_source(
        self,
        project_id: str,
        source_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        active: Optional[bool] = None,
        processing_info: Optional[Dict[str, Any]] = None,
        embedding_info: Optional[Dict[str, Any]] = None,
        summary_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update a source's metadata.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            name: New display name (optional)
            description: New description (optional)
            status: New status (optional)
            active: Whether source is included in chat context (optional)
            processing_info: Processing details (optional)
            embedding_info: Embedding details (optional)
            summary_info: Summary details (optional)

        Returns:
            Updated source metadata or None if not found
        """
        # Build updates dict with non-None values
        updates = {}

        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if status is not None:
            updates["status"] = status
            # Auto-activate when status becomes ready
            if status == "ready":
                updates["active"] = True
        if active is not None:
            updates["active"] = active
        if processing_info is not None:
            updates["processing_info"] = processing_info
        if embedding_info is not None:
            updates["embedding_info"] = embedding_info
        if summary_info is not None:
            updates["summary_info"] = summary_info

        result = source_index_service.update_source_in_index(project_id, source_id, updates)

        if result:
            print(f"Updated source: {source_id}")

        return result

    def delete_source(self, project_id: str, source_id: str) -> bool:
        """
        Delete a source, its raw file, processed content, and embeddings.

        Educational Note: When deleting a source, we clean up:
        1. Raw file (original upload)
        2. Processed file (extracted text)
        3. Chunk files (individual page files)
        4. Pinecone vectors (via embedding_service)

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            True if deleted, False if not found
        """
        source = self.get_source(project_id, source_id)
        if not source:
            return False

        # Delete embeddings and chunk files (if any)
        if source.get("embedding_info", {}).get("is_embedded"):
            try:
                from app.services.ai_services.embedding_service import embedding_service
                chunks_dir = get_chunks_dir(project_id)
                embedding_service.delete_embeddings(
                    project_id=project_id,
                    source_id=source_id,
                    chunks_dir=chunks_dir
                )
            except Exception as e:
                print(f"Error deleting embeddings for {source_id}: {e}")

        # Delete the raw file
        file_path = get_raw_dir(project_id) / source["stored_filename"]
        if file_path.exists():
            file_path.unlink()

        # Delete the processed file (if exists)
        processed_path = get_processed_dir(project_id) / f"{source_id}.txt"
        if processed_path.exists():
            processed_path.unlink()

        # Remove from index
        source_index_service.remove_source_from_index(project_id, source_id)

        print(f"Deleted source: {source_id}")

        return True

    def get_sources_summary(self, project_id: str) -> Dict[str, Any]:
        """
        Get a summary of sources for a project.

        Returns:
            Dictionary with source counts by category and total size
        """
        sources = self.list_sources(project_id)

        summary = {
            "total_count": len(sources),
            "total_size": sum(s.get("file_size", 0) for s in sources),
            "by_category": {},
            "by_status": {}
        }

        for source in sources:
            # Count by category
            category = source.get("category", "unknown")
            if category not in summary["by_category"]:
                summary["by_category"][category] = 0
            summary["by_category"][category] += 1

            # Count by status
            status = source.get("status", "unknown")
            if status not in summary["by_status"]:
                summary["by_status"][status] = 0
            summary["by_status"][status] += 1

        return summary

    def get_allowed_extensions(self) -> dict:
        """
        Get the allowed file extensions and their categories.

        Returns:
            Dictionary mapping extensions to categories
        """
        return ALLOWED_EXTENSIONS.copy()

    # =========================================================================
    # Source Upload/Creation (delegates to source_upload module)
    # =========================================================================

    def upload_source(
        self,
        project_id: str,
        file: FileStorage,
        name: Optional[str] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Upload a new source file to a project.

        Delegates to source_upload.file_upload module.
        """
        return upload_file(project_id, file, name, description)

    def create_source_from_file(
        self,
        project_id: str,
        file_path: Path,
        name: str,
        original_filename: str,
        category: str,
        mime_type: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Create a source entry from an already-saved file.

        Delegates to source_upload.file_upload module.
        """
        return create_from_existing_file(
            project_id, file_path, name, original_filename,
            category, mime_type, description
        )

    def add_url_source(
        self,
        project_id: str,
        url: str,
        name: Optional[str] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Add a URL source (website or YouTube link) to a project.

        Delegates to source_upload.url_upload module.
        """
        return upload_url(project_id, url, name, description)

    def add_text_source(
        self,
        project_id: str,
        content: str,
        name: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Add a pasted text source to a project.

        Delegates to source_upload.text_upload module.
        """
        return upload_text(project_id, content, name, description)

    def add_research_source(
        self,
        project_id: str,
        topic: str,
        description: str,
        links: List[str] = None
    ) -> Dict[str, Any]:
        """
        Add a deep research source to a project.

        Delegates to source_upload.research_upload module.
        """
        return upload_research(project_id, topic, description, links)

    def upload_database(
        self,
        project_id: str,
        name: str,
        connection_string: str
    ) -> Dict[str, Any]:
        """
        Add a database connection as a source to a project.

        Delegates to source_upload.database_upload module.
        """
        return upload_database(project_id, name, connection_string)

    # =========================================================================
    # Processing Delegation (thin wrappers)
    # =========================================================================

    def cancel_processing(self, project_id: str, source_id: str) -> bool:
        """
        Cancel processing for a source.

        Delegates to source_processing_service.
        """
        from app.services.source_services.source_processing import source_processing_service
        return source_processing_service.cancel_processing(project_id, source_id)

    def retry_processing(self, project_id: str, source_id: str) -> Dict[str, Any]:
        """
        Retry processing for a source that failed or was cancelled.

        Delegates to source_processing_service.
        """
        from app.services.source_services.source_processing import source_processing_service
        return source_processing_service.retry_processing(project_id, source_id)

    # =========================================================================
    # Path utilities (for backwards compatibility with processing services)
    # =========================================================================

    def _get_raw_dir(self, project_id: str) -> Path:
        """Get raw directory - uses path_utils."""
        return get_raw_dir(project_id)

    def _get_processed_dir(self, project_id: str) -> Path:
        """Get processed directory - uses path_utils."""
        return get_processed_dir(project_id)

    def _get_chunks_dir(self, project_id: str) -> Path:
        """Get chunks directory - uses path_utils."""
        return get_chunks_dir(project_id)


# Singleton instance
source_service = SourceService()
