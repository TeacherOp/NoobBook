"""
PDF Processor - Handles PDF file processing.

Educational Note: Uses pdf_service which processes PDFs in PARALLEL using
ThreadPoolExecutor. Result is either "ready" (all pages succeeded) or "error".
No partial status - we either succeed completely or fail completely.

Storage: Processed content is stored in Supabase Storage. Chunks are also
stored in Supabase Storage for RAG retrieval.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.services.integrations.supabase import storage_service
from app.utils.embedding_utils import needs_embedding
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service


def process_pdf(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process a PDF file - extract text and optionally create embeddings.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the raw PDF file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status and processing info
    """
    from app.services.ai_services.pdf_service import pdf_service

    result = pdf_service.extract_text_from_pdf(
        project_id=project_id,
        source_id=source_id,
        pdf_path=raw_file_path
    )

    if result.get("success"):
        # All pages extracted successfully
        processing_info = {
            "processor": "pdf_service_parallel",
            "model_used": result.get("model_used"),
            "total_pages": result.get("total_pages"),
            "pages_processed": result.get("pages_processed"),
            "character_count": result.get("character_count"),
            "token_usage": result.get("token_usage"),
            "extracted_at": result.get("extracted_at"),
            "parallel_workers": result.get("parallel_workers")
        }

        # Process embeddings if needed
        embedding_info = _process_embeddings(
            project_id=project_id,
            source_id=source_id,
            source_name=source.get("name", ""),
            source_service=source_service
        )

        # Generate summary after embeddings
        source_metadata = {**source, "processing_info": processing_info, "embedding_info": embedding_info}
        summary_info = _generate_summary(project_id, source_id, source_metadata)

        source_service.update_source(
            project_id,
            source_id,
            status="ready",
            processing_info=processing_info,
            embedding_info=embedding_info,
            summary_info=summary_info if summary_info else None
        )
        return {"success": True, "status": "ready"}

    elif result.get("status") == "cancelled":
        # Processing was cancelled by user
        source_service.update_source(
            project_id,
            source_id,
            status="uploaded",
            processing_info={
                "cancelled": True,
                "cancelled_at": datetime.now().isoformat(),
                "total_pages": result.get("total_pages")
            }
        )
        return {"success": False, "status": "cancelled", "error": "Processing cancelled"}

    else:
        # Extraction failed - no partial content kept
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={
                "error": result.get("error"),
                "failed_pages": result.get("failed_pages"),
                "total_pages": result.get("total_pages")
            }
        )
        return {"success": False, "error": result.get("error")}


def _process_embeddings(
    project_id: str,
    source_id: str,
    source_name: str,
    source_service
) -> Dict[str, Any]:
    """
    Process embeddings for a source after text extraction.

    Educational Note: We ALWAYS chunk and embed every source for consistent
    retrieval. The token count is used for chunk sizing decisions.

    Storage: Processed text is downloaded from Supabase Storage. Chunks are
    uploaded to Supabase Storage after processing.
    """
    # Download processed text from Supabase Storage
    processed_text = storage_service.download_processed_file(project_id, source_id)

    if not processed_text:
        return {
            "is_embedded": False,
            "embedded_at": None,
            "token_count": 0,
            "chunk_count": 0,
            "reason": "Processed text file not found in Supabase Storage"
        }

    try:
        # Get embedding info (always embeds, token count used for chunking)
        _, token_count, reason = needs_embedding(text=processed_text)

        # Update status to "embedding" before starting
        source_service.update_source(project_id, source_id, status="embedding")
        print(f"Starting embedding for {source_name} ({reason})")

        # Process embeddings using the embedding service
        # Note: embedding_service now uploads chunks to Supabase Storage
        return embedding_service.process_embeddings(
            project_id=project_id,
            source_id=source_id,
            source_name=source_name,
            processed_text=processed_text
        )

    except Exception as e:
        print(f"Error processing embeddings for {source_id}: {e}")
        return {
            "is_embedded": False,
            "embedded_at": None,
            "token_count": 0,
            "chunk_count": 0,
            "reason": f"Embedding error: {str(e)}"
        }


def _generate_summary(
    project_id: str,
    source_id: str,
    source_metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate a summary for a processed source."""
    try:
        print(f"Generating summary for source: {source_id}")
        result = summary_service.generate_summary(
            project_id=project_id,
            source_id=source_id,
            source_metadata=source_metadata
        )
        if result:
            print(f"Summary generated for {source_id}: {len(result.get('summary', ''))} chars")
            return result
        return {}
    except Exception as e:
        print(f"Error generating summary for {source_id}: {e}")
        return {}
