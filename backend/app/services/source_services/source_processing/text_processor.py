"""
Text Processor - Handles plain text file processing.

Educational Note: Text files don't have logical page boundaries like PDFs.
We store the entire content as a single "page" and let token-based chunking
handle the splitting for embeddings.

This creates a single page marker: === TEXT PAGE 1 of 1 ===
Token-based chunking then splits into ~200 token chunks for embeddings.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.utils.text import build_processed_output
from app.utils.embedding_utils import needs_embedding, count_tokens
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service
from app.services.integrations.supabase import storage_service


def process_text(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process a text file - upload to Supabase Storage for chunking.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the raw text file (temp file downloaded from Supabase)
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    # Read raw content
    with open(raw_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    source_name = source.get("name", "unknown")

    # Text files don't have logical page boundaries
    # Pass entire content as single page, let token-based chunking handle splits
    pages = [content]

    # Calculate token count for metadata
    token_count = count_tokens(content)

    # Build metadata for TEXT type
    metadata = {
        "character_count": len(content),
        "token_count": token_count
    }

    # Use centralized build_processed_output for consistent format
    processed_content = build_processed_output(
        pages=pages,
        source_type="TEXT",
        source_name=source_name,
        metadata=metadata
    )

    # Upload processed content to Supabase Storage
    storage_path = storage_service.upload_processed_file(
        project_id=project_id,
        source_id=source_id,
        content=processed_content
    )

    if not storage_path:
        raise ValueError("Failed to upload processed text to storage")

    processing_info = {
        "processor": "text_processor",
        "character_count": len(content),
        "token_count": token_count,
        "total_pages": 1,
        "extracted_at": datetime.now().isoformat()
    }

    # Process embeddings if needed
    embedding_info = _process_embeddings(
        project_id=project_id,
        source_id=source_id,
        source_name=source_name,
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
