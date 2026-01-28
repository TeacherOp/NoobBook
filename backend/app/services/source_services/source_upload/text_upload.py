"""
Text Upload Handler - Manages pasted text source uploads to Supabase Storage.

Educational Note: Pasted text is uploaded to Supabase Storage as a .txt file.
This is the simplest source type - the raw content IS the processed content
(after adding page markers for large texts).
"""
import uuid
from datetime import datetime
from typing import Dict, Any

from app.services.source_services import source_index_service
from app.services.background_services import task_service
from app.services.integrations.supabase import storage_service


def upload_text(
    project_id: str,
    content: str,
    name: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Add a pasted text source to a project (uploads to Supabase Storage).

    Educational Note: Pasted text is uploaded to Supabase Storage as a .txt file.
    Processing will add page markers for large texts.

    Args:
        project_id: The project UUID
        content: The pasted text content
        name: Display name for the source (required)
        description: Optional description

    Returns:
        Source metadata dictionary

    Raises:
        ValueError: If content or name is empty
    """
    # Validate inputs
    if not content or not content.strip():
        raise ValueError("Content cannot be empty")

    if not name or not name.strip():
        raise ValueError("Name is required for pasted text")

    content = content.strip()
    name = name.strip()

    # Generate source ID and filename
    source_id = str(uuid.uuid4())
    stored_filename = f"{source_id}.txt"

    # Convert content to bytes for upload
    file_data = content.encode('utf-8')
    file_size = len(file_data)

    # Upload to Supabase Storage
    storage_path = storage_service.upload_raw_file(
        project_id=project_id,
        source_id=source_id,
        filename=stored_filename,
        file_data=file_data,
        content_type="text/plain"
    )

    if not storage_path:
        raise ValueError("Failed to upload text to storage")

    # Create source metadata (matching file_upload.py format)
    source_metadata = {
        "id": source_id,
        "project_id": project_id,
        "name": name,
        "description": description,
        "type": "TEXT",
        "status": "uploaded",
        "raw_file_path": storage_path,
        "file_size": file_size,
        "is_active": False,
        "embedding_info": {
            "original_filename": f"{name}.txt",
            "mime_type": "text/plain",
            "file_extension": ".txt",
            "stored_filename": stored_filename,
            "source_type": "pasted_text"
        }
    }

    # Add to Supabase sources table
    source_index_service.add_source_to_index(project_id, source_metadata)

    print(f"Uploaded text source to Supabase: {name} ({source_id})")

    # Submit processing as background task
    _submit_processing_task(project_id, source_id)

    return source_metadata


def _submit_processing_task(project_id: str, source_id: str) -> None:
    """
    Submit a background task to process the text source.

    Educational Note: Even text files go through processing to add
    page markers for consistent chunking behavior.
    """
    try:
        from app.services.source_services.source_processing import source_processing_service
        from app.services.source_services import source_service

        task_id = task_service.submit_task(
            "source_processing",
            source_id,
            source_processing_service.process_source,
            project_id,
            source_id
        )

        # Update status to "processing" immediately
        source_service.update_source(project_id, source_id, status="processing")
    except Exception as e:
        print(f"ERROR: Failed to submit text processing task: {e}")
