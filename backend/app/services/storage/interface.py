"""
Storage Service Interface - Contract for file storage operations.

Educational Note: This interface defines all file operations needed for
NoobBook. Both local filesystem and Supabase Storage implementations
provide these methods with the same signatures.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, BinaryIO, Union


class StorageServiceInterface(ABC):
    """
    Interface for storage service operations.

    All paths are relative to project context. The implementation handles
    the actual storage location (local filesystem or cloud bucket).
    """

    # =========================================================================
    # File Operations
    # =========================================================================

    @abstractmethod
    def upload_file(
        self,
        project_id: str,
        category: str,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to storage.

        Args:
            project_id: The project UUID
            category: Storage category (raw, processed, chunks, studio/audio, etc.)
            file_data: File content as bytes or file-like object
            filename: Name for the stored file
            content_type: Optional MIME type

        Returns:
            Storage path of the uploaded file
        """
        raise NotImplementedError

    @abstractmethod
    def download_file(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Optional[bytes]:
        """
        Download a file from storage.

        Args:
            project_id: The project UUID
            category: Storage category
            filename: Name of the file to download

        Returns:
            File content as bytes, or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete_file(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> bool:
        """
        Delete a file from storage.

        Args:
            project_id: The project UUID
            category: Storage category
            filename: Name of the file to delete

        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError

    @abstractmethod
    def file_exists(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> bool:
        """
        Check if a file exists in storage.

        Args:
            project_id: The project UUID
            category: Storage category
            filename: Name of the file

        Returns:
            True if file exists
        """
        raise NotImplementedError

    @abstractmethod
    def list_files(
        self,
        project_id: str,
        category: str,
        prefix: Optional[str] = None
    ) -> List[str]:
        """
        List files in a storage category.

        Args:
            project_id: The project UUID
            category: Storage category
            prefix: Optional prefix to filter files

        Returns:
            List of filenames
        """
        raise NotImplementedError

    # =========================================================================
    # Directory Operations
    # =========================================================================

    @abstractmethod
    def delete_directory(
        self,
        project_id: str,
        category: str,
        directory: Optional[str] = None
    ) -> int:
        """
        Delete a directory and all its contents.

        Args:
            project_id: The project UUID
            category: Storage category
            directory: Optional subdirectory within category

        Returns:
            Number of files deleted
        """
        raise NotImplementedError

    @abstractmethod
    def delete_project_files(self, project_id: str) -> int:
        """
        Delete all files for a project.

        Args:
            project_id: The project UUID

        Returns:
            Number of files deleted
        """
        raise NotImplementedError

    # =========================================================================
    # URL Generation (for serving files)
    # =========================================================================

    @abstractmethod
    def get_file_url(
        self,
        project_id: str,
        category: str,
        filename: str,
        expires_in: int = 3600
    ) -> Optional[str]:
        """
        Get a URL for accessing a file.

        For local storage, this returns a path that can be served.
        For Supabase, this returns a signed URL.

        Args:
            project_id: The project UUID
            category: Storage category
            filename: Name of the file
            expires_in: URL expiration in seconds (for signed URLs)

        Returns:
            URL string or None if file not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_local_path(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Optional[Path]:
        """
        Get the local filesystem path for a file.

        For local storage, returns the actual path.
        For Supabase, downloads to temp and returns temp path.

        Args:
            project_id: The project UUID
            category: Storage category
            filename: Name of the file

        Returns:
            Path object or None if not available
        """
        raise NotImplementedError

    # =========================================================================
    # Chunk-specific Operations
    # =========================================================================

    @abstractmethod
    def save_chunk(
        self,
        project_id: str,
        source_id: str,
        chunk_id: str,
        content: str
    ) -> str:
        """
        Save a text chunk for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            chunk_id: The chunk ID
            content: Chunk text content

        Returns:
            Storage path of the chunk
        """
        raise NotImplementedError

    @abstractmethod
    def load_chunk(
        self,
        project_id: str,
        source_id: str,
        chunk_id: str
    ) -> Optional[str]:
        """
        Load a text chunk.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            chunk_id: The chunk ID

        Returns:
            Chunk text content or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def delete_source_chunks(
        self,
        project_id: str,
        source_id: str
    ) -> int:
        """
        Delete all chunks for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Number of chunks deleted
        """
        raise NotImplementedError
