"""
Supabase Storage Service - File upload/download operations.

Educational Note: Supabase Storage provides S3-compatible file storage.
Files are organized in buckets:
- raw-files: Original uploaded files (PDFs, images, audio)
- processed-files: Extracted text content
- chunks: Text chunks for RAG search
- studio-outputs: Generated content (audio, video, documents)

File paths follow the pattern: {project_id}/{source_id}/{filename}
"""
from typing import Optional, BinaryIO, List, Dict, Any
from pathlib import Path

from app.services.integrations.supabase import get_supabase, is_supabase_enabled


# Bucket names
BUCKET_RAW = "raw-files"
BUCKET_PROCESSED = "processed-files"
BUCKET_CHUNKS = "chunks"
BUCKET_STUDIO = "studio-outputs"


def _get_client():
    """Get Supabase client, raising error if not configured."""
    if not is_supabase_enabled():
        raise RuntimeError(
            "Supabase is not configured. Please add SUPABASE_URL and "
            "SUPABASE_ANON_KEY to your .env file."
        )
    return get_supabase()


def _build_path(project_id: str, source_id: str, filename: str) -> str:
    """Build storage path: project_id/source_id/filename"""
    return f"{project_id}/{source_id}/{filename}"


# =============================================================================
# RAW FILES (Original uploads)
# =============================================================================

def upload_raw_file(
    project_id: str,
    source_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a raw file to storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename
        file_data: File bytes
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_RAW).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        print(f"  Uploaded raw file: {path}")
        return path
    except Exception as e:
        print(f"  Error uploading raw file: {e}")
        return None


def download_raw_file(project_id: str, source_id: str, filename: str) -> Optional[bytes]:
    """
    Download a raw file from storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename

    Returns:
        File bytes or None if not found
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_RAW).download(path)
        return response
    except Exception as e:
        print(f"  Error downloading raw file: {e}")
        return None


def delete_raw_file(project_id: str, source_id: str, filename: str) -> bool:
    """Delete a raw file from storage."""
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_RAW).remove([path])
        print(f"  Deleted raw file: {path}")
        return True
    except Exception as e:
        print(f"  Error deleting raw file: {e}")
        return False


def get_raw_file_url(project_id: str, source_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
    """
    Get a signed URL for a raw file.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_RAW).create_signed_url(path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        print(f"  Error getting signed URL: {e}")
        return None


# =============================================================================
# PROCESSED FILES (Extracted text)
# =============================================================================

def upload_processed_file(
    project_id: str,
    source_id: str,
    content: str
) -> Optional[str]:
    """
    Upload processed text content to storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        content: Extracted text content

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    filename = f"{source_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_PROCESSED).upload(
            path=path,
            file=content.encode("utf-8"),
            file_options={"content-type": "text/plain; charset=utf-8"}
        )
        print(f"  Uploaded processed file: {path}")
        return path
    except Exception as e:
        print(f"  Error uploading processed file: {e}")
        return None


def download_processed_file(project_id: str, source_id: str) -> Optional[str]:
    """
    Download processed text content from storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        Text content or None if not found
    """
    client = _get_client()
    filename = f"{source_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_PROCESSED).download(path)
        return response.decode("utf-8")
    except Exception as e:
        print(f"  Error downloading processed file: {e}")
        return None


def delete_processed_file(project_id: str, source_id: str) -> bool:
    """Delete a processed file from storage."""
    client = _get_client()
    filename = f"{source_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_PROCESSED).remove([path])
        return True
    except Exception as e:
        print(f"  Error deleting processed file: {e}")
        return False


# =============================================================================
# CHUNKS (Text chunks for RAG)
# =============================================================================

def upload_chunk(
    project_id: str,
    source_id: str,
    chunk_id: str,
    content: str
) -> Optional[str]:
    """
    Upload a text chunk to storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        chunk_id: The chunk ID (e.g., source_id_page_1_chunk_1)
        content: Chunk text content

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    filename = f"{chunk_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_CHUNKS).upload(
            path=path,
            file=content.encode("utf-8"),
            file_options={"content-type": "text/plain; charset=utf-8"}
        )
        return path
    except Exception as e:
        print(f"  Error uploading chunk: {e}")
        return None


def download_chunk(project_id: str, source_id: str, chunk_id: str) -> Optional[str]:
    """
    Download a text chunk from storage.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        chunk_id: The chunk ID

    Returns:
        Chunk text content or None if not found
    """
    client = _get_client()
    filename = f"{chunk_id}.txt"
    path = _build_path(project_id, source_id, filename)

    try:
        response = client.storage.from_(BUCKET_CHUNKS).download(path)
        return response.decode("utf-8")
    except Exception as e:
        print(f"  Error downloading chunk: {e}")
        return None


def list_source_chunks(project_id: str, source_id: str) -> List[Dict[str, Any]]:
    """
    List and download all chunks for a source.

    Educational Note: This function retrieves all chunks from Supabase Storage
    for use in RAG search. Returns chunk data in the same format as the old
    local file-based system for compatibility.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        List of chunk dicts with chunk_id, text, page_number, source_id
    """
    client = _get_client()
    prefix = f"{project_id}/{source_id}"

    try:
        # List all files in the source's chunk folder
        files = client.storage.from_(BUCKET_CHUNKS).list(prefix)
        if not files:
            return []

        chunks = []
        for file_info in files:
            filename = file_info.get("name", "")
            if not filename.endswith(".txt"):
                continue

            # Extract chunk_id from filename (remove .txt)
            chunk_id = filename[:-4]

            # Download chunk content
            path = f"{prefix}/{filename}"
            try:
                response = client.storage.from_(BUCKET_CHUNKS).download(path)
                text = response.decode("utf-8")

                # Parse page number from chunk_id
                # Format: {source_id}_page_{page}_chunk_{n}
                page_number = 1
                if "_page_" in chunk_id:
                    try:
                        page_part = chunk_id.split("_page_")[1]
                        page_number = int(page_part.split("_chunk_")[0])
                    except (IndexError, ValueError):
                        pass

                chunks.append({
                    "chunk_id": chunk_id,
                    "text": text,
                    "page_number": page_number,
                    "source_id": source_id
                })
            except Exception as e:
                print(f"  Error downloading chunk {chunk_id}: {e}")
                continue

        # Sort by chunk_id for consistent ordering
        chunks.sort(key=lambda c: c.get("chunk_id", ""))
        return chunks

    except Exception as e:
        print(f"  Error listing chunks: {e}")
        return []


def delete_source_chunks(project_id: str, source_id: str) -> bool:
    """
    Delete all chunks for a source.

    Args:
        project_id: The project UUID
        source_id: The source UUID

    Returns:
        True if successful
    """
    client = _get_client()
    prefix = f"{project_id}/{source_id}/"

    try:
        # List all files with prefix
        files = client.storage.from_(BUCKET_CHUNKS).list(prefix)
        if files:
            paths = [f"{prefix}{f['name']}" for f in files]
            client.storage.from_(BUCKET_CHUNKS).remove(paths)
        return True
    except Exception as e:
        print(f"  Error deleting chunks: {e}")
        return False


# =============================================================================
# STUDIO OUTPUTS (Generated content - PRDs, blogs, emails, etc.)
# =============================================================================

def _build_studio_path(project_id: str, job_type: str, job_id: str, filename: str) -> str:
    """
    Build storage path for studio outputs.
    Pattern: {project_id}/{job_type}/{job_id}/{filename}
    Example: abc123/prds/def456/def456.md
    """
    return f"{project_id}/{job_type}/{job_id}/{filename}"


def upload_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    content: str,
    content_type: str = "text/plain; charset=utf-8"
) -> Optional[str]:
    """
    Upload a studio output file to storage.

    Args:
        project_id: The project UUID
        job_type: Type of studio output (prds, blogs, emails, etc.)
        job_id: The job UUID
        filename: Output filename (e.g., job_id.md)
        content: File content as string
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        # Try to upload (will fail if file exists)
        client.storage.from_(BUCKET_STUDIO).upload(
            path=path,
            file=content.encode("utf-8"),
            file_options={"content-type": content_type}
        )
        print(f"  Uploaded studio file: {path}")
        return path
    except Exception as e:
        # If file exists, try to update it
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            try:
                client.storage.from_(BUCKET_STUDIO).update(
                    path=path,
                    file=content.encode("utf-8"),
                    file_options={"content-type": content_type}
                )
                print(f"  Updated studio file: {path}")
                return path
            except Exception as update_e:
                print(f"  Error updating studio file: {update_e}")
                return None
        print(f"  Error uploading studio file: {e}")
        return None


def append_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    content: str
) -> Optional[str]:
    """
    Append content to an existing studio file.

    Educational Note: Supabase Storage doesn't support append, so we
    download existing content, append new content, then re-upload.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename
        content: Content to append

    Returns:
        Storage path if successful, None otherwise
    """
    # Download existing content
    existing = download_studio_file(project_id, job_type, job_id, filename)

    if existing is None:
        # File doesn't exist, create new
        return upload_studio_file(project_id, job_type, job_id, filename, content)

    # Append and re-upload
    new_content = existing + content
    return upload_studio_file(project_id, job_type, job_id, filename, new_content)


def download_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> Optional[str]:
    """
    Download a studio output file from storage.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename

    Returns:
        File content as string or None if not found
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).download(path)
        return response.decode("utf-8")
    except Exception as e:
        print(f"  Error downloading studio file: {e}")
        return None


def delete_studio_file(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> bool:
    """Delete a studio output file from storage."""
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        client.storage.from_(BUCKET_STUDIO).remove([path])
        print(f"  Deleted studio file: {path}")
        return True
    except Exception as e:
        print(f"  Error deleting studio file: {e}")
        return False


def delete_studio_job_files(project_id: str, job_type: str, job_id: str) -> bool:
    """
    Delete all files for a studio job.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID

    Returns:
        True if successful
    """
    client = _get_client()
    prefix = f"{project_id}/{job_type}/{job_id}"

    try:
        # List all files in the job folder
        files = client.storage.from_(BUCKET_STUDIO).list(prefix)
        if files:
            paths = [f"{prefix}/{f['name']}" for f in files]
            client.storage.from_(BUCKET_STUDIO).remove(paths)
            print(f"  Deleted {len(paths)} studio files for job {job_id}")
        return True
    except Exception as e:
        print(f"  Error deleting studio job files: {e}")
        return False


def upload_studio_binary(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a binary file (image, video, etc.) to studio outputs in Supabase.

    Args:
        project_id: The project UUID
        job_type: Type of studio output (blogs, etc.)
        job_id: The job UUID
        filename: Output filename (e.g., image.png)
        file_data: Binary file data
        content_type: MIME type (e.g., image/png)

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        client.storage.from_(BUCKET_STUDIO).upload(
            path=path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        print(f"  Uploaded studio binary: {path}")
        return path
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            try:
                client.storage.from_(BUCKET_STUDIO).update(
                    path=path,
                    file=file_data,
                    file_options={"content-type": content_type}
                )
                print(f"  Updated studio binary: {path}")
                return path
            except Exception as update_e:
                print(f"  Error updating studio binary: {update_e}")
                return None
        print(f"  Error uploading studio binary: {e}")
        return None


def download_studio_binary(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> Optional[bytes]:
    """
    Download a binary file from Supabase studio outputs.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename

    Returns:
        File bytes or None if not found
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).download(path)
        return response
    except Exception as e:
        print(f"  Error downloading studio binary: {e}")
        return None


def get_studio_public_url(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str
) -> str:
    """
    Get the public URL for a studio file.

    Educational Note: This returns a direct public URL if bucket is public,
    otherwise use get_studio_signed_url for private buckets.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename

    Returns:
        Public URL string
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).get_public_url(path)
        return response
    except Exception as e:
        print(f"  Error getting public URL: {e}")
        return ""


def get_studio_signed_url(
    project_id: str,
    job_type: str,
    job_id: str,
    filename: str,
    expires_in: int = 3600
) -> Optional[str]:
    """
    Get a signed URL for a studio file (for private buckets).

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID
        filename: Output filename
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = _build_studio_path(project_id, job_type, job_id, filename)

    try:
        response = client.storage.from_(BUCKET_STUDIO).create_signed_url(path, expires_in)
        return response.get("signedURL")
    except Exception as e:
        print(f"  Error getting signed URL: {e}")
        return None


# =============================================================================
# CLEANUP - Delete all files for a source
# =============================================================================

def delete_source_files(project_id: str, source_id: str, filename: str) -> bool:
    """
    Delete all files associated with a source.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename for raw file

    Returns:
        True if all deletions successful
    """
    results = []

    # Delete raw file
    results.append(delete_raw_file(project_id, source_id, filename))

    # Delete processed file
    results.append(delete_processed_file(project_id, source_id))

    # Delete chunks
    results.append(delete_source_chunks(project_id, source_id))

    return all(results)
