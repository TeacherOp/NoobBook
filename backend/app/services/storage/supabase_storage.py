"""
Supabase Storage Service - Cloud-based implementation.

Educational Note: This implementation uses Supabase Storage (S3-compatible)
for file storage. Files are organized in buckets with project-based paths.

Bucket Structure:
    sources/
    ├── {project_id}/raw/{filename}
    ├── {project_id}/processed/{source_id}.txt
    └── {project_id}/chunks/{source_id}/{chunk_id}.txt

    studio/
    ├── {project_id}/audio/{job_id}.mp3
    └── {project_id}/scripts/{job_id}.txt

    ai-outputs/
    └── {project_id}/images/{filename}
"""
import tempfile
from pathlib import Path
from typing import Optional, List, BinaryIO, Union

from app.config.supabase import get_supabase_storage, get_supabase_config
from app.services.storage.interface import StorageServiceInterface


class SupabaseStorageService(StorageServiceInterface):
    """
    Supabase Storage implementation of storage service.

    Educational Note: Supabase Storage uses buckets (like S3) with
    a flat namespace. We encode the project structure in the path.
    """

    def __init__(self):
        """Initialize with Supabase storage client."""
        self._storage = None
        self._config = get_supabase_config()

    @property
    def storage(self):
        """Lazy-load storage client."""
        if self._storage is None:
            self._storage = get_supabase_storage()
            if self._storage is None:
                raise RuntimeError("Supabase storage not available")
        return self._storage

    def _get_bucket_and_path(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> tuple:
        """
        Map category to bucket and construct storage path.

        Returns:
            Tuple of (bucket_name, storage_path)
        """
        # Map categories to buckets
        if category.startswith("studio"):
            bucket = self._config.studio_bucket
            sub_path = category.replace("studio/", "") if "/" in category else ""
            path = f"{project_id}/{sub_path}/{filename}".replace("//", "/")
        elif category.startswith("ai_outputs"):
            bucket = self._config.ai_outputs_bucket
            sub_path = category.replace("ai_outputs/", "") if "/" in category else ""
            path = f"{project_id}/{sub_path}/{filename}".replace("//", "/")
        else:
            # raw, processed, chunks go to sources bucket
            bucket = self._config.sources_bucket
            path = f"{project_id}/{category}/{filename}"

        return bucket, path

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
        """Upload a file to Supabase Storage."""
        bucket, path = self._get_bucket_and_path(project_id, category, filename)

        # Convert file-like object to bytes if needed
        if not isinstance(file_data, bytes):
            file_data = file_data.read()

        options = {}
        if content_type:
            options["content-type"] = content_type

        self.storage.from_(bucket).upload(
            path,
            file_data,
            file_options=options
        )

        return f"{bucket}/{path}"

    def download_file(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Optional[bytes]:
        """Download a file from Supabase Storage."""
        bucket, path = self._get_bucket_and_path(project_id, category, filename)

        try:
            response = self.storage.from_(bucket).download(path)
            return response
        except Exception as e:
            print(f"Error downloading file {path}: {e}")
            return None

    def delete_file(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> bool:
        """Delete a file from Supabase Storage."""
        bucket, path = self._get_bucket_and_path(project_id, category, filename)

        try:
            self.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            print(f"Error deleting file {path}: {e}")
            return False

    def file_exists(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> bool:
        """Check if a file exists in Supabase Storage."""
        bucket, path = self._get_bucket_and_path(project_id, category, filename)

        try:
            # List with the exact path to check existence
            result = self.storage.from_(bucket).list(
                path=path.rsplit('/', 1)[0] if '/' in path else '',
                options={"search": filename}
            )
            return len(result) > 0
        except Exception:
            return False

    def list_files(
        self,
        project_id: str,
        category: str,
        prefix: Optional[str] = None
    ) -> List[str]:
        """List files in a category."""
        bucket, base_path = self._get_bucket_and_path(project_id, category, "")
        base_path = base_path.rstrip('/')

        try:
            options = {}
            if prefix:
                options["search"] = prefix

            result = self.storage.from_(bucket).list(path=base_path, options=options)
            return [item["name"] for item in result if item.get("name")]
        except Exception as e:
            print(f"Error listing files in {base_path}: {e}")
            return []

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
        bucket, base_path = self._get_bucket_and_path(project_id, category, "")

        if directory:
            base_path = f"{base_path.rstrip('/')}/{directory}"

        try:
            # List all files in the directory
            files = self.storage.from_(bucket).list(path=base_path)

            if not files:
                return 0

            # Delete all files
            paths = [f"{base_path}/{f['name']}" for f in files if f.get("name")]
            if paths:
                self.storage.from_(bucket).remove(paths)

            return len(paths)
        except Exception as e:
            print(f"Error deleting directory {base_path}: {e}")
            return 0

    def delete_project_files(self, project_id: str) -> int:
        """Delete all files for a project."""
        total = 0

        # Delete from all buckets
        for bucket in [
            self._config.sources_bucket,
            self._config.studio_bucket,
            self._config.ai_outputs_bucket
        ]:
            try:
                # List all files under project_id
                files = self.storage.from_(bucket).list(path=project_id)

                if files:
                    # Recursively list all files
                    all_paths = self._list_all_files(bucket, project_id)
                    if all_paths:
                        self.storage.from_(bucket).remove(all_paths)
                        total += len(all_paths)
            except Exception as e:
                print(f"Error deleting project files from {bucket}: {e}")

        return total

    def _list_all_files(self, bucket: str, path: str) -> List[str]:
        """Recursively list all files under a path."""
        all_files = []

        try:
            items = self.storage.from_(bucket).list(path=path)

            for item in items:
                item_path = f"{path}/{item['name']}"
                if item.get("id"):  # It's a file
                    all_files.append(item_path)
                else:  # It's a folder
                    all_files.extend(self._list_all_files(bucket, item_path))
        except Exception:
            pass

        return all_files

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
        """Get a signed URL for accessing a file."""
        bucket, path = self._get_bucket_and_path(project_id, category, filename)

        try:
            result = self.storage.from_(bucket).create_signed_url(
                path,
                expires_in
            )
            return result.get("signedURL")
        except Exception as e:
            print(f"Error creating signed URL for {path}: {e}")
            return None

    def get_local_path(
        self,
        project_id: str,
        category: str,
        filename: str
    ) -> Optional[Path]:
        """
        Download file to temp directory and return path.

        Educational Note: For Supabase storage, we download to a temp file
        when local path is needed (e.g., for processing).
        """
        data = self.download_file(project_id, category, filename)

        if data is None:
            return None

        # Create temp file with same extension
        suffix = Path(filename).suffix
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        )
        temp_file.write(data)
        temp_file.close()

        return Path(temp_file.name)

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
        bucket = self._config.sources_bucket
        path = f"{project_id}/chunks/{source_id}/{chunk_id}.txt"

        self.storage.from_(bucket).upload(
            path,
            content.encode('utf-8'),
            file_options={"content-type": "text/plain"}
        )

        return f"{bucket}/{path}"

    def load_chunk(
        self,
        project_id: str,
        source_id: str,
        chunk_id: str
    ) -> Optional[str]:
        """Load a text chunk."""
        bucket = self._config.sources_bucket
        path = f"{project_id}/chunks/{source_id}/{chunk_id}.txt"

        try:
            data = self.storage.from_(bucket).download(path)
            return data.decode('utf-8')
        except Exception:
            return None

    def delete_source_chunks(
        self,
        project_id: str,
        source_id: str
    ) -> int:
        """Delete all chunks for a source."""
        bucket = self._config.sources_bucket
        path = f"{project_id}/chunks/{source_id}"

        try:
            files = self.storage.from_(bucket).list(path=path)
            if not files:
                return 0

            paths = [f"{path}/{f['name']}" for f in files if f.get("name")]
            if paths:
                self.storage.from_(bucket).remove(paths)

            return len(paths)
        except Exception as e:
            print(f"Error deleting chunks for {source_id}: {e}")
            return 0
