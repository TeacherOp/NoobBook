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
import logging
import os
from typing import Optional, BinaryIO, List, Dict, Any, Union
from pathlib import Path

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


def _rewrite_signed_url_for_browser(signed_url: Optional[str]) -> Optional[str]:
    """
    Swap the internal host on a Supabase signed URL for a browser-reachable
    one so the PDF / image / audio preview actually loads.

    Self-hosted Supabase signs URLs with whatever host is in SUPABASE_URL —
    usually the internal Docker hostname like ``http://kong:8000``. The
    browser can't resolve that, so the preview fails with a generic
    "Failed to load …".

    Resolution order for the public host:

    1. The *current request's* origin (``request.host_url``). If we got
       called inside an HTTP handler, the user's browser by definition
       reached us at that origin — and our nginx config proxies
       ``/storage/*`` to Kong on the same origin, so the same host serves
       both API and storage. No config required.
    2. ``SUPABASE_PUBLIC_URL`` env var, for callers outside the request
       context (background jobs, CLI tasks).

    No-op when the URL doesn't start with the internal host (already
    public) — keeps local dev, where ``SUPABASE_URL=http://localhost:8000``
    is already browser-reachable, working without changes.
    """
    if not signed_url:
        return signed_url
    internal = os.getenv("SUPABASE_URL")
    if not internal or not signed_url.startswith(internal):
        return signed_url

    public: Optional[str] = None
    try:
        # Local import: avoid a hard Flask dependency at module load so
        # this service stays usable in non-request contexts (workers).
        from flask import request, has_request_context

        if has_request_context():
            public = (request.host_url or "").rstrip("/")
    except Exception:  # pragma: no cover — defensive
        public = None

    if not public:
        public = (os.getenv("SUPABASE_PUBLIC_URL") or "").rstrip("/")

    if not public or public == internal:
        return signed_url
    return public + signed_url[len(internal):]


# Bucket names
BUCKET_RAW = "raw-files"
BUCKET_PROCESSED = "processed-files"
BUCKET_CHUNKS = "chunks"
BUCKET_STUDIO = "studio-outputs"
BUCKET_BRAND_ASSETS = "brand-assets"
# Transient inline images pasted/dropped into the chat input. Stored
# permanently for chat-history rendering, but cleared when the chat is
# deleted (cascade). Distinct from raw-files so RLS policies and
# cleanup-on-chat-delete stay simple (single-prefix remove).
BUCKET_CHAT_ATTACHMENTS = "chat-attachments"

# Supabase storage3 defaults to limit=100 which silently drops entries.
# Use a high limit to ensure we list all files in a folder.
_LIST_OPTIONS = {"limit": 10000}


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


def _upsert_file(client, bucket: str, path: str, file_data, file_options: dict) -> str:
    """
    Upload a file, replacing it if it already exists.

    Educational Note: We use remove + upload instead of .update() because
    the Supabase storage3 .update() method can fail with MissingContentMD5
    due to a boto3/botocore dependency issue. Remove + upload is more reliable.

    Returns:
        The storage path on success.

    Raises:
        Exception on failure.
    """
    try:
        client.storage.from_(bucket).upload(
            path=path,
            file=file_data,
            file_options=file_options,
        )
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            # File exists — remove first, then re-upload
            client.storage.from_(bucket).remove([path])
            client.storage.from_(bucket).upload(
                path=path,
                file=file_data,
                file_options=file_options,
            )
        else:
            raise
    return path


# =============================================================================
# RAW FILES (Original uploads)
# =============================================================================

# Module-level cache of the last upload failure's underlying exception
# message. Set by upload_raw_file when both streaming and buffered
# attempts fail; consumed by callers (chunked finalize, etc.) so the
# user-facing 500 can include the real reason instead of "see logs".
# Single string is fine — uploads are serialized per source_id, and
# the caller reads it immediately after the failed call.
_last_upload_error: Optional[str] = None


def get_last_upload_error() -> Optional[str]:
    """Return the underlying exception message from the most recent
    upload_raw_file failure, or ``None`` if the last call succeeded."""
    return _last_upload_error


def upload_raw_file(
    project_id: str,
    source_id: str,
    filename: str,
    file_data: Union[bytes, BinaryIO],
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a raw file to storage.

    Robustness layers (in order):
      1. Streaming upload (preferred — keeps multi-GB files off the heap).
      2. On failure, fall back to a buffered bytes upload. SpooledTemporaryFile
         streams can break storage3/httpx for some file shapes (no
         Content-Length, partial reads, weird encodings); reading into bytes
         sidesteps the SDK quirks at the cost of memory for that one file.
      3. On Duplicate / "already exists" errors, remove the existing object
         then retry, mirroring the studio uploader's _upsert_file pattern.
         This recovers retries that hit the same source_id path.

    Returns the storage path on success. Returns None **only** after every
    fallback fails — and the underlying exception is logged with full
    context so the API layer can surface a useful error to the user.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        filename: Original filename
        file_data: File bytes OR a file-like object (preferred for large uploads
                   to avoid loading the whole file into memory)
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise.
    """
    client = _get_client()
    path = _build_path(project_id, source_id, filename)
    file_options = {"content-type": content_type}

    # Reset before this attempt so a stale message from a prior failure
    # doesn't leak into a callsite that succeeds.
    global _last_upload_error
    _last_upload_error = None

    def _do_upload(payload):
        try:
            client.storage.from_(BUCKET_RAW).upload(
                path=path,
                file=payload,
                file_options=file_options,
            )
            return None
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate" in msg or "already exists" in msg or "resource already exists" in msg:
                # Remove the orphaned object then retry once. Don't recurse —
                # if the retry also fails we want to surface that error.
                try:
                    client.storage.from_(BUCKET_RAW).remove([path])
                except Exception as remove_exc:
                    logger.warning("Could not remove existing raw file %s: %s", path, remove_exc)
                client.storage.from_(BUCKET_RAW).upload(
                    path=path,
                    file=payload,
                    file_options=file_options,
                )
                return None
            return exc

    # Attempt 1: streaming upload (file-like objects only — bytes go straight
    # to attempt 2's payload regardless).
    streaming_error: Optional[Exception] = None
    if not isinstance(file_data, (bytes, bytearray)):
        try:
            err = _do_upload(file_data)
            if err is None:
                return path
            streaming_error = err
        except Exception as exc:
            streaming_error = exc

        if streaming_error is not None:
            logger.warning(
                "Streaming upload of %s failed (%s) — retrying as buffered bytes",
                path, streaming_error,
            )
            # Rewind the stream before re-reading. Some streams may not be
            # seekable; if so we'll surface the failure on the bytes attempt.
            try:
                file_data.seek(0)
            except Exception:
                pass

    # Attempt 2: buffered bytes. Works for both retries (file-like that we
    # just rewound) and the original bytes-input path.
    try:
        if isinstance(file_data, (bytes, bytearray)):
            payload = bytes(file_data)
        else:
            payload = file_data.read()
        err = _do_upload(payload)
        if err is None:
            return path
        logger.error(
            "Buffered upload of %s failed: %s (size=%d, content_type=%s)",
            path, err, len(payload), content_type,
        )
        _last_upload_error = str(err)
        return None
    except Exception as exc:
        logger.error(
            "Failed to upload raw file %s: %s (streaming_error=%s)",
            path, exc, streaming_error,
        )
        _last_upload_error = str(exc)
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
        logger.error("Failed to download raw file %s: %s", path, e)
        return None


def delete_raw_file(project_id: str, source_id: str, filename: str) -> bool:
    """Delete a raw file from storage."""
    client = _get_client()
    path = _build_path(project_id, source_id, filename)

    try:
        client.storage.from_(BUCKET_RAW).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete raw file %s: %s", path, e)
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
        return _rewrite_signed_url_for_browser(response.get("signedURL"))
    except Exception as e:
        logger.error("Failed to get signed URL for %s: %s", path, e)
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
        return path
    except Exception as e:
        logger.error("Failed to upload processed file %s: %s", path, e)
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
        logger.error("Failed to download processed file %s: %s", path, e)
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
        logger.error("Failed to delete processed file %s: %s", path, e)
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
        logger.error("Failed to upload chunk %s: %s", path, e)
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
        logger.error("Failed to download chunk %s: %s", path, e)
        return None


def list_source_chunks(project_id: str, source_id: str) -> List[Dict[str, Any]]:
    """
    List and download all chunks for a source.

    Educational Note: This function retrieves all chunks from Supabase Storage
    for use in RAG search. Returns chunk data as a list of dicts with
    chunk_id, text, page_number, and source_id.

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
        files = client.storage.from_(BUCKET_CHUNKS).list(
            prefix, options=_LIST_OPTIONS
        )
        if not files:
            return []

        # Filter to .txt files only
        txt_files = [f for f in files if f.get("name", "").endswith(".txt")]
        if not txt_files:
            return []

        def _download_chunk(file_info):
            """Download a single chunk file and parse its metadata."""
            filename = file_info["name"]
            chunk_id = filename[:-4]  # Remove .txt
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

                return {
                    "chunk_id": chunk_id,
                    "text": text,
                    "page_number": page_number,
                    "source_id": source_id
                }
            except Exception as e:
                logger.error("Failed to download chunk %s: %s", chunk_id, e)
                return None

        # Download chunks concurrently to avoid N+1 sequential requests
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(_download_chunk, txt_files))

        chunks = [r for r in results if r is not None]

        # Sort by chunk_id for consistent ordering
        chunks.sort(key=lambda c: c.get("chunk_id", ""))
        return chunks

    except Exception as e:
        logger.error("Failed to list chunks for %s: %s", prefix, e)
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
        files = client.storage.from_(BUCKET_CHUNKS).list(
            prefix, options=_LIST_OPTIONS
        )
        if files:
            paths = [f"{prefix}{f['name']}" for f in files]
            client.storage.from_(BUCKET_CHUNKS).remove(paths)
        return True
    except Exception as e:
        logger.error("Failed to delete chunks for %s: %s", prefix, e)
        return False


# =============================================================================
# CHAT ATTACHMENTS (Inline images pasted/dropped into the chat input)
# =============================================================================
#
# Transient screenshots / images attached to a chat message — distinct from
# Sources because they're one-shot context, not RAG-indexed knowledge. Layout:
#
#   {project_id}/{chat_id}/{attachment_id}/{filename}
#
# Cleanup-on-chat-delete is a single-prefix remove (cascade-safe).

def _build_chat_attachment_path(
    project_id: str, chat_id: str, attachment_id: str, filename: str
) -> str:
    return f"{project_id}/{chat_id}/{attachment_id}/{filename}"


def upload_chat_attachment(
    project_id: str,
    chat_id: str,
    attachment_id: str,
    filename: str,
    file_data: Union[bytes, BinaryIO],
    content_type: str = "application/octet-stream",
) -> Optional[str]:
    """
    Upload an inline chat attachment (typically a screenshot pasted/dropped
    into the chat input). Returns the storage path on success.

    Mirrors the upload_raw_file shape but writes to the chat-attachments
    bucket and uses a chat-scoped path prefix so cascade-delete on chat
    removal is a single prefix wipe.
    """
    client = _get_client()
    path = _build_chat_attachment_path(project_id, chat_id, attachment_id, filename)
    file_options = {"content-type": content_type}

    try:
        if not isinstance(file_data, (bytes, bytearray)):
            try:
                payload = file_data.read()
            except Exception:
                payload = file_data
        else:
            payload = bytes(file_data)
        client.storage.from_(BUCKET_CHAT_ATTACHMENTS).upload(
            path=path,
            file=payload,
            file_options=file_options,
        )
        return path
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate" in msg or "already exists" in msg:
            try:
                client.storage.from_(BUCKET_CHAT_ATTACHMENTS).remove([path])
                client.storage.from_(BUCKET_CHAT_ATTACHMENTS).upload(
                    path=path, file=payload, file_options=file_options,
                )
                return path
            except Exception as retry_exc:
                logger.error("Chat-attachment retry upload failed for %s: %s", path, retry_exc)
                return None
        logger.error("Failed to upload chat attachment %s: %s", path, exc)
        return None


def download_chat_attachment(path: str) -> Optional[bytes]:
    """
    Download a chat attachment by full storage path. Used by the chat
    pipeline when building Claude vision payloads (fresh base64 per send).
    """
    client = _get_client()
    try:
        return client.storage.from_(BUCKET_CHAT_ATTACHMENTS).download(path)
    except Exception as e:
        logger.error("Failed to download chat attachment %s: %s", path, e)
        return None


def get_chat_attachment_url(path: str, expires_in: int = 3600) -> Optional[str]:
    """Signed URL for in-app chat-history rendering."""
    client = _get_client()
    try:
        response = client.storage.from_(BUCKET_CHAT_ATTACHMENTS).create_signed_url(path, expires_in)
        return _rewrite_signed_url_for_browser(response.get("signedURL"))
    except Exception as e:
        logger.error("Failed to get signed URL for chat attachment %s: %s", path, e)
        return None


def delete_chat_attachment(path: str) -> bool:
    """
    Delete a single chat attachment by its full storage path. Used for
    rollback when the message-stream multipart upload fails partway —
    so a failed third-of-three upload doesn't leak the first two.
    Returns True on success / not-found, False on a real error.
    """
    client = _get_client()
    try:
        client.storage.from_(BUCKET_CHAT_ATTACHMENTS).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete chat attachment %s: %s", path, e)
        return False


def delete_chat_attachments_for_chat(project_id: str, chat_id: str) -> bool:
    """
    Cascade-delete every attachment under a chat's prefix. Called from
    chat_service.delete_chat to keep storage in sync with the messages
    cascade. Idempotent — empty prefix is a no-op success.
    """
    client = _get_client()
    prefix = f"{project_id}/{chat_id}/"

    try:
        # The bucket layout is {project_id}/{chat_id}/{attachment_id}/{filename}
        # so list returns the per-attachment dirs at this depth — recurse one
        # level via list-with-prefix to get the actual file paths to remove.
        attachment_dirs = client.storage.from_(BUCKET_CHAT_ATTACHMENTS).list(
            prefix.rstrip("/"), options=_LIST_OPTIONS
        ) or []
        all_paths: List[str] = []
        for entry in attachment_dirs:
            sub_prefix = f"{prefix}{entry['name']}/"
            files = client.storage.from_(BUCKET_CHAT_ATTACHMENTS).list(
                sub_prefix.rstrip("/"), options=_LIST_OPTIONS
            ) or []
            all_paths.extend(f"{sub_prefix}{f['name']}" for f in files)
        if all_paths:
            client.storage.from_(BUCKET_CHAT_ATTACHMENTS).remove(all_paths)
        return True
    except Exception as e:
        logger.error("Failed to delete chat attachments for %s: %s", prefix, e)
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
        return _upsert_file(
            client, BUCKET_STUDIO, path,
            content.encode("utf-8"),
            {"content-type": content_type},
        )
    except Exception as e:
        logger.error("Failed to upload studio file %s: %s", path, e)
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
        logger.error("Failed to download studio file %s: %s", path, e)
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
        return True
    except Exception as e:
        logger.error("Failed to delete studio file %s: %s", path, e)
        return False


def delete_studio_job_files(project_id: str, job_type: str, job_id: str) -> bool:
    """
    Delete all files for a studio job, including subdirectories.

    Educational Note: Supabase .list() only returns immediate children.
    For jobs with subdirectories (e.g., websites with assets/, presentations
    with slides/ and screenshots/), we iterate through folders to find all files.

    Args:
        project_id: The project UUID
        job_type: Type of studio output
        job_id: The job UUID

    Returns:
        True if successful
    """
    client = _get_client()
    root_prefix = f"{project_id}/{job_type}/{job_id}"

    try:
        # Iteratively scan folders to collect all file paths
        folders_to_scan = [root_prefix]
        all_paths = []

        while folders_to_scan:
            folder = folders_to_scan.pop()
            entries = client.storage.from_(BUCKET_STUDIO).list(
                folder, options=_LIST_OPTIONS
            )
            if not entries:
                continue
            for entry in entries:
                path = f"{folder}/{entry['name']}"
                if entry.get("id") is None:
                    # No id means it's a folder — recurse into it
                    folders_to_scan.append(path)
                else:
                    all_paths.append(path)

        if all_paths:
            client.storage.from_(BUCKET_STUDIO).remove(all_paths)
        return True
    except Exception as e:
        logger.error("Failed to delete studio job files for %s: %s", job_id, e)
        return False


def list_studio_job_files(project_id: str, job_type: str, job_id: str) -> List[Dict[str, Any]]:
    """
    List all files for a studio job, including subdirectories.

    Educational Note: Used for ZIP downloads (websites, presentations) where
    we need to enumerate all files in the job folder. Iterates through
    subdirectories since Supabase .list() only returns immediate children.

    Args:
        project_id: The project UUID
        job_type: Type of studio output (websites, presentations, etc.)
        job_id: The job UUID

    Returns:
        List of file info dicts with 'name' as relative path from job root,
        or empty list on error
    """
    client = _get_client()
    root_prefix = f"{project_id}/{job_type}/{job_id}"

    try:
        # Iteratively scan folders to collect all files
        folders_to_scan = [root_prefix]
        all_files = []

        while folders_to_scan:
            folder = folders_to_scan.pop()
            entries = client.storage.from_(BUCKET_STUDIO).list(
                folder, options=_LIST_OPTIONS
            )
            if not entries:
                continue
            for entry in entries:
                path = f"{folder}/{entry['name']}"
                if entry.get("id") is None:
                    # No id means it's a folder — recurse into it
                    folders_to_scan.append(path)
                else:
                    # Store with relative path from job root for ZIP structure
                    relative_path = path[len(root_prefix) + 1:]  # Strip prefix + /
                    file_info = {**entry, "name": relative_path}
                    all_files.append(file_info)

        return all_files
    except Exception as e:
        logger.error("Failed to list studio job files for %s: %s", root_prefix, e)
        return []


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
        return _upsert_file(
            client, BUCKET_STUDIO, path,
            file_data,
            {"content-type": content_type},
        )
    except Exception as e:
        logger.error("Failed to upload studio binary %s: %s", path, e)
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
        logger.error("Failed to download studio binary %s: %s", path, e)
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
        logger.error("Failed to get public URL for %s: %s", path, e)
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
        return _rewrite_signed_url_for_browser(response.get("signedURL"))
    except Exception as e:
        logger.error("Failed to get signed URL for %s: %s", path, e)
        return None


# =============================================================================
# AI IMAGES (Generated charts/plots from analysis)
# =============================================================================

def upload_ai_image(
    project_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "image/png"
) -> Optional[str]:
    """
    Upload an AI-generated image to the studio-outputs bucket.

    Educational Note: AI-generated images (e.g., matplotlib charts from
    CSV analysis) are stored in Supabase Storage instead of local disk.
    Path pattern: {project_id}/ai-images/{filename}

    Args:
        project_id: The project UUID
        filename: Image filename (e.g., source_id_plot_uuid.png)
        file_data: Image bytes
        content_type: MIME type (default image/png)

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = f"{project_id}/ai-images/{filename}"

    try:
        return _upsert_file(
            client, BUCKET_STUDIO, path,
            file_data,
            {"content-type": content_type},
        )
    except Exception as e:
        logger.error("Failed to upload AI image %s: %s", path, e)
        return None


def download_ai_image(project_id: str, filename: str) -> Optional[bytes]:
    """
    Download an AI-generated image from the studio-outputs bucket.

    Args:
        project_id: The project UUID
        filename: Image filename

    Returns:
        Image bytes or None if not found
    """
    client = _get_client()
    path = f"{project_id}/ai-images/{filename}"

    try:
        response = client.storage.from_(BUCKET_STUDIO).download(path)
        return response
    except Exception as e:
        logger.error("Failed to download AI image %s: %s", path, e)
        return None


def get_ai_image_url(
    project_id: str,
    filename: str,
    expires_in: int = 3600
) -> Optional[str]:
    """
    Get a signed URL for an AI-generated image.

    Args:
        project_id: The project UUID
        filename: Image filename
        expires_in: URL expiration in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = f"{project_id}/ai-images/{filename}"

    try:
        response = client.storage.from_(BUCKET_STUDIO).create_signed_url(path, expires_in)
        return _rewrite_signed_url_for_browser(response.get("signedURL"))
    except Exception as e:
        logger.error("Failed to get AI image URL for %s: %s", path, e)
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


# =============================================================================
# BRAND ASSETS (Logos, icons, fonts, images for brand kit)
# =============================================================================

def _build_brand_path(user_id: str, asset_id: str, filename: str) -> str:
    """
    Build storage path for brand assets.
    Pattern: {user_id}/brand/{asset_id}/{filename}
    Example: abc123/brand/def456/logo.svg
    """
    return f"{user_id}/brand/{asset_id}/{filename}"


def upload_brand_asset(
    user_id: str,
    asset_id: str,
    filename: str,
    file_data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload a brand asset file to storage.

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename (e.g., logo.svg)
        file_data: File bytes
        content_type: MIME type

    Returns:
        Storage path if successful, None otherwise
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        return _upsert_file(
            client, BUCKET_BRAND_ASSETS, path,
            file_data,
            {"content-type": content_type},
        )
    except Exception as e:
        logger.error("Failed to upload brand asset %s: %s", path, e)
        return None


def download_brand_asset(
    user_id: str,
    asset_id: str,
    filename: str
) -> Optional[bytes]:
    """
    Download a brand asset file from storage.

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename

    Returns:
        File bytes or None if not found
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        response = client.storage.from_(BUCKET_BRAND_ASSETS).download(path)
        return response
    except Exception as e:
        logger.error("Failed to download brand asset %s: %s", path, e)
        return None


def delete_brand_asset(
    user_id: str,
    asset_id: str,
    filename: str
) -> bool:
    """
    Delete a brand asset file from storage.

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename

    Returns:
        True if successful
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        client.storage.from_(BUCKET_BRAND_ASSETS).remove([path])
        return True
    except Exception as e:
        logger.error("Failed to delete brand asset %s: %s", path, e)
        return False


def get_brand_asset_url(
    user_id: str,
    asset_id: str,
    filename: str,
    expires_in: int = 3600
) -> Optional[str]:
    """
    Get a signed URL for a brand asset (for private bucket access).

    Args:
        user_id: The user UUID
        asset_id: The brand asset UUID
        filename: Asset filename
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        Signed URL or None
    """
    client = _get_client()
    path = _build_brand_path(user_id, asset_id, filename)

    try:
        response = client.storage.from_(BUCKET_BRAND_ASSETS).create_signed_url(path, expires_in)
        return _rewrite_signed_url_for_browser(response.get("signedURL"))
    except Exception as e:
        logger.error("Failed to get brand asset signed URL for %s: %s", path, e)
        return None


def delete_user_brand_assets(user_id: str) -> bool:
    """
    Delete all brand assets for a user.

    Educational Note: Uses iterative folder scanning because Supabase .list()
    only returns immediate children. Folders have id=None, files have a UUID id.

    Args:
        user_id: The user UUID

    Returns:
        True if successful
    """
    client = _get_client()
    root_prefix = f"{user_id}/brand"

    try:
        # Iteratively scan folders to collect all file paths
        folders_to_scan = [root_prefix]
        all_paths = []

        while folders_to_scan:
            folder = folders_to_scan.pop()
            entries = client.storage.from_(BUCKET_BRAND_ASSETS).list(
                folder, options=_LIST_OPTIONS
            )
            if not entries:
                continue
            for entry in entries:
                path = f"{folder}/{entry['name']}"
                if entry.get("id") is None:
                    # No id means it's a folder — recurse into it
                    folders_to_scan.append(path)
                else:
                    all_paths.append(path)

        if all_paths:
            client.storage.from_(BUCKET_BRAND_ASSETS).remove(all_paths)
        return True
    except Exception as e:
        logger.error("Failed to delete brand assets for user %s: %s", user_id, e)
        return False
