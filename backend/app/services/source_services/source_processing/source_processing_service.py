"""
Source Processing Service - Orchestrates processing for different source types.

Educational Note: This service is a simple dispatcher that routes sources
to the appropriate processor based on file type. Each processor handles:
- Type-specific content extraction
- Embedding generation (if needed)
- Summary generation

Processing Flow:
    1. Source uploaded -> status: "uploaded"
    2. Processing starts -> status: "processing"
    3. If embeddings needed -> status: "embedding"
    4. Complete -> status: "ready" | "error"

The actual processing logic lives in the individual processor modules:
- pdf_processor.py
- text_processor.py
- docx_processor.py
- image_processor.py
- pptx_processor.py
- audio_processor.py
- link_processor.py (also handles YouTube via youtube_processor)
- research_processor.py (deep research via AI agent)

Storage: Files are stored in Supabase Storage and downloaded to temp
directories for processing. Processed content is uploaded back to Supabase.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import tempfile
import shutil

from app.services.integrations.supabase import storage_service


class SourceProcessingService:
    """
    Service class for orchestrating source file processing.

    Educational Note: This service dispatches to the appropriate processor
    based on file extension. Processing is typically run in background threads.
    """

    # File extension to processor mapping
    PROCESSOR_MAP = {
        ".pdf": "pdf",
        ".txt": "text",
        ".docx": "docx",
        ".csv": "csv",  # CSV files (including Google Sheets exports)
        ".jpeg": "image",
        ".jpg": "image",
        ".png": "image",
        ".gif": "image",
        ".webp": "image",
        ".pptx": "pptx",
        ".mp3": "audio",
        ".wav": "audio",
        ".m4a": "audio",
        ".aac": "audio",
        ".flac": "audio",
        ".link": "link",  # Handles both website URLs and YouTube
        ".research": "research",  # Deep research source
    }

    def process_source(self, project_id: str, source_id: str) -> Dict[str, Any]:
        """
        Process a source file by dispatching to the appropriate processor.

        Educational Note: This method acts as a router - it determines the
        file type and calls the corresponding processor module. Each processor
        is responsible for:
        1. Extracting content (using AI services or direct parsing)
        2. Creating embeddings (if content is large enough)
        3. Generating a summary
        4. Updating the source status

        Storage Flow:
        1. Download raw file from Supabase Storage to temp directory
        2. Process the file (extract text, create embeddings, etc.)
        3. Upload processed content to Supabase Storage
        4. Clean up temp files

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Dict with success status and processing info
        """
        print(f"DEBUG: process_source called for project={project_id}, source={source_id}")

        # Import here to avoid circular imports
        from app.services.source_services import source_service

        source = source_service.get_source(project_id, source_id)
        print(f"DEBUG: Got source: {source is not None}")
        if not source:
            return {"success": False, "error": "Source not found"}

        # Get file info from embedding_info (stored during upload)
        embedding_info = source.get("embedding_info", {})
        file_ext = embedding_info.get("file_extension", "").lower()
        stored_filename = embedding_info.get("stored_filename", "")

        if not stored_filename:
            return {"success": False, "error": "Source has no stored filename"}

        # Update status to processing
        source_service.update_source(project_id, source_id, status="processing")

        # Create temp directory for processing
        temp_dir = Path(tempfile.mkdtemp(prefix=f"noobbook_{source_id}_"))

        try:
            # Download raw file from Supabase Storage to temp directory
            print(f"Downloading file from Supabase Storage: {stored_filename}")
            file_data = storage_service.download_raw_file(
                project_id=project_id,
                source_id=source_id,
                filename=stored_filename
            )

            if not file_data:
                raise ValueError(f"Failed to download file from storage: {stored_filename}")

            # Write to temp file
            raw_file_path = temp_dir / stored_filename
            with open(raw_file_path, 'wb') as f:
                f.write(file_data)
            print(f"File downloaded to temp: {raw_file_path}")

            # Determine which processor to use
            processor_type = self.PROCESSOR_MAP.get(file_ext)

            if processor_type == "pdf":
                from app.services.source_services.source_processing.pdf_processor import process_pdf
                return process_pdf(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "text":
                from app.services.source_services.source_processing.text_processor import process_text
                return process_text(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "docx":
                from app.services.source_services.source_processing.docx_processor import process_docx
                return process_docx(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "csv":
                from app.services.source_services.source_processing.csv_processor import process_csv
                return process_csv(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "image":
                from app.services.source_services.source_processing.image_processor import process_image
                return process_image(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "pptx":
                from app.services.source_services.source_processing.pptx_processor import process_pptx
                return process_pptx(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "audio":
                from app.services.source_services.source_processing.audio_processor import process_audio
                return process_audio(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "link":
                from app.services.source_services.source_processing.link_processor import process_link
                return process_link(project_id, source_id, source, raw_file_path, source_service)

            elif processor_type == "research":
                from app.services.source_services.source_processing.research_processor import process_research
                return process_research(project_id, source_id, source, raw_file_path, source_service)

            else:
                # Unsupported file type
                source_service.update_source(
                    project_id,
                    source_id,
                    status="uploaded",
                    processing_info={"note": "Processing not yet supported for this file type"}
                )
                return {"success": True, "status": "uploaded", "note": "No processing needed"}

        except Exception as e:
            print(f"Error processing source {source_id}: {e}")
            source_service.update_source(
                project_id,
                source_id,
                status="error",
                processing_info={"error": str(e)}
            )
            return {"success": False, "error": str(e)}

        finally:
            # Clean up temp directory
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    print(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    print(f"Warning: Could not clean up temp directory {temp_dir}: {e}")

    def cancel_processing(self, project_id: str, source_id: str) -> bool:
        """
        Cancel processing for a source.

        Educational Note: This cancels any running tasks for the source and
        cleans up processed data from Supabase Storage, but keeps the raw file
        so user can retry.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            True if cancellation was initiated, False otherwise
        """
        from app.services.source_services import source_service
        from app.services.background_services import task_service

        source = source_service.get_source(project_id, source_id)
        if not source:
            return False

        # Only cancel if currently processing or embedding
        if source["status"] not in ["uploaded", "processing", "embedding"]:
            return False

        # Cancel any running tasks for this source
        cancelled_count = task_service.cancel_tasks_for_target(source_id)
        print(f"Cancelled {cancelled_count} tasks for source {source_id}")

        # Delete processed file from Supabase Storage (keep raw file!)
        storage_service.delete_processed_file(project_id, source_id)
        print(f"Deleted partial processed file from Supabase Storage")

        # Delete any chunks from Supabase Storage
        storage_service.delete_source_chunks(project_id, source_id)
        print(f"Deleted partial chunks from Supabase Storage")

        # Update source status to uploaded (ready to retry)
        source_service.update_source(
            project_id,
            source_id,
            status="uploaded",
            processing_info={"cancelled": True, "cancelled_at": datetime.now().isoformat()}
        )

        return True

    def retry_processing(self, project_id: str, source_id: str) -> Dict[str, Any]:
        """
        Retry processing for a source that failed or was cancelled.

        Educational Note: This submits a new processing task for the source.
        Only works for sources that have a raw file in Supabase Storage but
        are not currently processing.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Dict with success status and message
        """
        from app.services.source_services import source_service
        from app.services.background_services import task_service

        source = source_service.get_source(project_id, source_id)
        if not source:
            return {"success": False, "error": "Source not found"}

        # Can only retry if status is uploaded or error (not processing/embedding)
        if source["status"] in ["processing", "embedding"]:
            return {"success": False, "error": "Source is already processing"}

        if source["status"] == "ready":
            return {"success": False, "error": "Source is already processed"}

        # Verify raw file exists in Supabase Storage
        embedding_info = source.get("embedding_info", {})
        stored_filename = embedding_info.get("stored_filename", "")

        if not stored_filename:
            return {"success": False, "error": "Source has no stored filename"}

        # Check if raw file exists in Supabase Storage
        raw_file_data = storage_service.download_raw_file(project_id, source_id, stored_filename)
        if not raw_file_data:
            return {"success": False, "error": "Raw file not found in storage"}

        # Delete any existing processed file from Supabase Storage
        storage_service.delete_processed_file(project_id, source_id)

        # Delete any existing chunks from Supabase Storage
        storage_service.delete_source_chunks(project_id, source_id)

        # Update status to uploaded (processing will be done by background task)
        source_service.update_source(
            project_id,
            source_id,
            status="uploaded",
            processing_info={"retry": True, "retry_at": datetime.now().isoformat()}
        )

        # Submit new processing task
        task_service.submit_task(
            "source_processing",
            source_id,
            self.process_source,
            project_id,
            source_id
        )

        return {"success": True, "message": "Processing restarted"}


# Singleton instance
source_processing_service = SourceProcessingService()
