"""
Image Processor - Handles image file processing.

Educational Note: image_service uses Claude's vision capability to
analyze images and extract structured content including text, visual
descriptions, data from charts/tables, and summaries.

Storage: Processed content is stored in Supabase Storage. Chunks are also
stored in Supabase Storage for RAG retrieval.
"""
from pathlib import Path
from typing import Dict, Any

from app.services.integrations.supabase import storage_service
from app.utils.embedding_utils import needs_embedding
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service


def process_image(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process an image file - extract content using Claude vision.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the raw image file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    from app.services.ai_services.image_service import image_service

    result = image_service.extract_content_from_image(
        project_id=project_id,
        source_id=source_id,
        image_path=raw_file_path
    )

    if result.get("success"):
        # Get processed content from result
        processed_content = result.get("processed_content", "")

        # Upload processed content to Supabase Storage
        storage_path = storage_service.upload_processed_file(
            project_id=project_id,
            source_id=source_id,
            content=processed_content
        )

        if not storage_path:
            source_service.update_source(
                project_id,
                source_id,
                status="error",
                processing_info={"error": "Failed to upload processed content to storage"}
            )
            return {"success": False, "error": "Failed to upload processed content to storage"}

        processing_info = {
            "processor": "image_service",
            "model_used": result.get("model_used"),
            "content_type": result.get("content_type"),
            "character_count": result.get("character_count"),
            "token_count": result.get("token_count"),
            "token_usage": result.get("token_usage"),
            "extracted_at": result.get("extracted_at")
        }

        # Process embeddings
        embedding_info = _process_embeddings(
            project_id=project_id,
            source_id=source_id,
            source_name=source.get("name", ""),
            processed_text=processed_content,
            source_service=source_service
        )

        # Generate summary after embeddings
        source_metadata = {**source, "processing_info": processing_info, "embedding_info": embedding_info}
        summary_info = _generate_summary(project_id, source_id, source_metadata)

        source_service.update_source(
            project_id,
            source_id,
            status="ready",
            active=True,  # Auto-activate when ready
            processing_info=processing_info,
            embedding_info=embedding_info,
            summary_info=summary_info if summary_info else None
        )
        return {"success": True, "status": "ready"}

    else:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": result.get("error")}
        )
        return {"success": False, "error": result.get("error")}


def _process_embeddings(
    project_id: str,
    source_id: str,
    source_name: str,
    processed_text: str,
    source_service
) -> Dict[str, Any]:
    """
    Process embeddings for a source using embedding_service.

    Educational Note: We ALWAYS chunk and embed every source for consistent
    retrieval. The token count is used for chunk sizing decisions.
    Chunks are uploaded to Supabase Storage.
    """
    try:
        # Get embedding info (always embeds, token count used for chunking)
        _, token_count, reason = needs_embedding(text=processed_text)

        # Update status to "embedding" before starting
        source_service.update_source(project_id, source_id, status="embedding")
        print(f"Starting embedding for {source_name} ({reason})")

        # Process embeddings using the embedding service
        # Chunks are automatically uploaded to Supabase Storage
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
