"""
File Upload Handler - Manages file uploads to Supabase Storage.

Educational Note: This module handles uploading files (PDF, DOCX, images, audio, etc.)
to Supabase Storage and creating source entries in the database.

Supports:
- Direct file uploads from the frontend
- Creating sources from already-saved files (e.g., Google Drive imports)
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from werkzeug.datastructures import FileStorage

from app.services.source_services import source_index_service
from app.services.background_services import task_service
from app.services.integrations.supabase import storage_service
from app.utils.file_utils import (
    ALLOWED_EXTENSIONS,
    is_allowed_file,
    get_file_info,
    validate_file_size,
)


def upload_file(
    project_id: str,
    file: FileStorage,
    name: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """
    Upload a new source file to Supabase Storage.

    Educational Note: This function:
    1. Validates the file type and size
    2. Uploads the file to Supabase Storage (raw-files bucket)
    3. Creates metadata in the sources table
    4. Triggers background processing

    Args:
        project_id: The project UUID
        file: The uploaded file (Flask FileStorage)
        name: Optional display name (defaults to original filename)
        description: Optional description of the source

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If file type is not allowed or file is empty
    """
    # Validate file
    if not file or not file.filename:
        raise ValueError("No file provided")

    original_filename = file.filename
    if not is_allowed_file(original_filename):
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS.keys()))
        raise ValueError(f"File type not allowed. Allowed types: {allowed}")

    # Get file info
    ext, category, mime_type = get_file_info(original_filename)

    # Generate source ID and filename
    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}{ext}"

    # Read file data
    file_data = file.read()
    file_size = len(file_data)

    # Validate file size (e.g., images have 5MB limit)
    size_error = validate_file_size(original_filename, file_size)
    if size_error:
        raise ValueError(size_error)

    # Upload to Supabase Storage
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type=mime_type
    )

    if not storage_path:
        raise ValueError("Failed to upload file to storage")

    # Create source metadata
    timestamp = datetime.now().isoformat()
    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": name or original_filename,
        "description": description,
        "type": category.upper(),  # PDF, IMAGE, AUDIO, etc.
        "status": "uploaded",
        "raw_file_path": storage_path,  # Supabase Storage path
        "file_size": file_size,
        "is_active": False,
        # Additional metadata stored in embedding_info
        "embedding_info": {
            "original_filename": original_filename,
            "mime_type": mime_type,
            "file_extension": ext,
            "stored_filename": stored_filename
        }
    }

    # Add to Supabase sources table
    source_index_service.add_source_to_index(project_id, source_metadata)

    print(f"Uploaded source to Supabase: {source_metadata['name']} ({source_id})", flush=True)

    # Submit processing as a background task
    print(f"DEBUG: About to submit processing task...", flush=True)
    _submit_processing_task(project_id, source_id)
    print(f"DEBUG: Processing task submitted, returning metadata", flush=True)

    return source_metadata


def create_from_existing_file(
    project_id: str,
    file_path: Path,
    name: str,
    original_filename: str,
    category: str,
    mime_type: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Create a source entry from an already-saved file (upload to Supabase).

    Educational Note: This is used when a file is downloaded/saved externally
    (e.g., from Google Drive) and we need to upload it to Supabase Storage.

    Args:
        project_id: The project UUID
        file_path: Path where the file is temporarily saved
        name: Display name for the source
        original_filename: Original filename (used for extension)
        category: Source category (document, image, audio, etc.)
        mime_type: MIME type of the file
        description: Optional description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If file does not exist or upload fails
    """
    if not file_path.exists():
        raise ValueError(f"File does not exist: {file_path}")

    # Get extension from original filename
    ext = Path(original_filename).suffix.lower()
    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}{ext}"

    # Read file data
    with open(file_path, 'rb') as f:
        file_data = f.read()
    file_size = len(file_data)

    # Upload to Supabase Storage
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type=mime_type
    )

    if not storage_path:
        raise ValueError("Failed to upload file to storage")

    # Delete temporary local file
    try:
        file_path.unlink()
    except Exception as e:
        print(f"  Warning: Could not delete temp file {file_path}: {e}")

    # Create source metadata
    timestamp = datetime.now().isoformat()
    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": name,
        "description": description,
        "type": category.upper(),
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": file_size,
        "is_active": False,
        "embedding_info": {
            "original_filename": original_filename,
            "mime_type": mime_type,
            "file_extension": ext,
            "stored_filename": stored_filename
        }
    }

    # Add to Supabase sources table
    source_index_service.add_source_to_index(project_id, source_metadata)

    print(f"Created source from file: {name} ({source_id})")

    # Submit processing as a background task
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """
    Submit a background task to process the source.

    Educational Note: We import source_processing_service here to avoid
    circular imports at module load time.
    """
    try:
        print(f"DEBUG: Submitting processing task for source {source_id}", flush=True)
        from app.services.source_services.source_processing import source_processing_service
        from app.services.source_services import source_service

        task_id = task_service.submit_task(
            "source_processing",
            source_id,
            source_processing_service.process_source,
            project_id,
            source_id
        )
        print(f"DEBUG: Task submitted successfully with ID {task_id}", flush=True)

        # Update status to "processing" immediately so frontend shows correct state
        source_service.update_source(project_id, source_id, status="processing")
        print(f"DEBUG: Status updated to 'processing' for source {source_id}", flush=True)
    except Exception as e:
        print(f"ERROR: Failed to submit processing task: {e}", flush=True)
        import traceback
        traceback.print_exc()
