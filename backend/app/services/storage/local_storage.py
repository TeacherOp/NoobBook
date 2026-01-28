"""
Local Storage Service - Filesystem-based implementation.

Educational Note: This implementation uses the local filesystem for storage,
maintaining compatibility with the existing NoobBook data structure.
Files are stored in data/projects/{project_id}/...
"""
import shutil
from pathlib import Path
from typing import Optional, List, BinaryIO, Union

from app.services.storage.interface import StorageServiceInterface
from app.utils.path_utils import (
    get_project_dir,
    get_raw_dir,
    get_processed_dir,
    get_chunks_dir,
    get_source_chunks_dir,
    get_studio_dir,
    get_studio_audio_dir,
    get_studio_scripts_dir,
    get_ai_outputs_dir,
    get_ai_images_dir,
)


class LocalStorageService(StorageServiceInterface):
    """
    Local filesystem implementation of storage service.

    This maintains the existing directory structure:
        data/projects/{project_id}/
        ├── sources/
        │   ├── raw/
        │   ├── processed/
        │   └── chunks/{source_id}/
        ├── studio/
        │   ├── audio/
        │   └── scripts/
        └── ai_outputs/
            └── images/
    """

    def _get_category_dir(self, project_id: str, category: str) -> Path:
        """
        Map category string to directory path.

        Args:
            project_id: The project UUID
            category: Storage category

        Returns:
            Path to the category directory
        """
        category_map = {
            "raw": get_raw_dir(project_id),
            "processed": get_processed_dir(project_id),
            "chunks": get_chunks_dir(project_id),
            "studio": get_studio_dir(project_id),
            "studio/audio": get_studio_audio_dir(project_id),
            "studio/scripts": get_studio_scripts_dir(project_id),
            "ai_outputs": get_ai_outputs_dir(project_id),
            "ai_outputs/images": get_ai_images_dir(project_id),
        }

        if category in category_map:
            return category_map[category]

        # Default: create subdirectory under project
        path = get_project_dir(project_id) / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_file_path(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Path:
        """Get the full path for a file."""
        category_dir = self._get_category_dir(project_id, category)
        return category_dir / filename

    # =========================================================================
    # File Operations
    # =========================================================================

    def upload_file(
        self,
        project_id: str,
        category: str,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: Optional[str] = None
    ) -> str:
        """Upload a file to local storage."""
        file_path = self._get_file_path(project_id, category, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(file_data, bytes):
            with open(file_path, 'wb') as f:
                f.write(file_data)
        else:
            # File-like object
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file_data, f)

        return str(file_path)

    def download_file(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Optional[bytes]:
        """Download a file from local storage."""
        file_path = self._get_file_path(project_id, category, filename)

        if not file_path.exists():
            return None

        with open(file_path, 'rb') as f:
            return f.read()

    def delete_file(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> bool:
        """Delete a file from local storage."""
        file_path = self._get_file_path(project_id, category, filename)

        if not file_path.exists():
            return False

        file_path.unlink()
        return True

    def file_exists(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> bool:
        """Check if a file exists."""
        file_path = self._get_file_path(project_id, category, filename)
        return file_path.exists()

    def list_files(
        self,
        project_id: str,
        category: str,
        prefix: Optional[str] = None
    ) -> List[str]:
        """List files in a category."""
        category_dir = self._get_category_dir(project_id, category)

        if not category_dir.exists():
            return []

        files = []
        for f in category_dir.iterdir():
            if f.is_file():
                if prefix is None or f.name.startswith(prefix):
                    files.append(f.name)

        return sorted(files)

    # =========================================================================
    # Directory Operations
    # =========================================================================

    def delete_directory(
        self,
        project_id: str,
        category: str,
        directory: Optional[str] = None
    ) -> int:
        """Delete a directory and all its contents."""
        category_dir = self._get_category_dir(project_id, category)

        if directory:
            target_dir = category_dir / directory
        else:
            target_dir = category_dir

        if not target_dir.exists():
            return 0

        count = sum(1 for _ in target_dir.rglob('*') if _.is_file())
        shutil.rmtree(target_dir)
        return count

    def delete_project_files(self, project_id: str) -> int:
        """Delete all files for a project."""
        project_dir = get_project_dir(project_id)

        if not project_dir.exists():
            return 0

        count = sum(1 for _ in project_dir.rglob('*') if _.is_file())
        shutil.rmtree(project_dir)
        return count

    # =========================================================================
    # URL Generation
    # =========================================================================

    def get_file_url(
        self,
        project_id: str,
        category: str,
        filename: str,
        expires_in: int = 3600
    ) -> Optional[str]:
        """
        Get a URL for accessing a file.

        For local storage, returns the relative path that can be served
        by the Flask app.
        """
        file_path = self._get_file_path(project_id, category, filename)

        if not file_path.exists():
            return None

        # Return relative URL path for Flask to serve
        # This depends on how the app serves static files
        return f"/api/v1/projects/{project_id}/files/{category}/{filename}"

    def get_local_path(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Optional[Path]:
        """Get the local filesystem path for a file."""
        file_path = self._get_file_path(project_id, category, filename)

        if not file_path.exists():
            return None

        return file_path

    # =========================================================================
    # Chunk-specific Operations
    # =========================================================================

    def save_chunk(
        self,
        project_id: str,
        source_id: str,
        chunk_id: str,
        content: str
    ) -> str:
        """Save a text chunk for a source."""
        chunks_dir = get_source_chunks_dir(project_id, source_id)
        chunk_path = chunks_dir / f"{chunk_id}.txt"

        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(chunk_path)

    def load_chunk(
        self,
        project_id: str,
        source_id: str,
        chunk_id: str
    ) -> Optional[str]:
        """Load a text chunk."""
        chunks_dir = get_source_chunks_dir(project_id, source_id)
        chunk_path = chunks_dir / f"{chunk_id}.txt"

        if not chunk_path.exists():
            return None

        with open(chunk_path, 'r', encoding='utf-8') as f:
            return f.read()

    def delete_source_chunks(
        self,
        project_id: str,
        source_id: str
    ) -> int:
        """Delete all chunks for a source."""
        chunks_dir = get_source_chunks_dir(project_id, source_id)

        if not chunks_dir.exists():
            return 0

        count = len(list(chunks_dir.glob('*.txt')))
        shutil.rmtree(chunks_dir)
        return count
