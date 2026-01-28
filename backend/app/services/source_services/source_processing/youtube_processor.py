"""
YouTube Processor - Handles YouTube video transcript extraction.

Educational Note: YouTube videos often have captions (manual or auto-generated)
that we can fetch directly without downloading the video. This is much faster
than audio transcription and uses existing caption data.

Transcript priority:
1. Manual captions (human-created, higher quality)
2. Auto-generated captions (YouTube's ASR)

Storage: Processed content is stored in Supabase Storage. Chunks are also
stored in Supabase Storage for RAG retrieval.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.utils.text import build_processed_output
from app.utils.embedding_utils import needs_embedding, count_tokens
from app.services.integrations.supabase import storage_service
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service


def process_youtube(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    url: str,
    link_data: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process a YouTube video - fetch transcript using youtube-transcript-api.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        url: The YouTube URL
        link_data: Data from the .link file
        raw_file_path: Path to the .link file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    from app.services.integrations.youtube import youtube_service

    # Fetch transcript
    result = youtube_service.get_transcript(url, include_timestamps=True)

    if not result.get("success"):
        error_msg = result.get("error_message", "Failed to fetch YouTube transcript")
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={
                "error": error_msg,
                "url": url,
                "video_id": result.get("video_id")
            }
        )
        return {"success": False, "error": error_msg}

    # Extract transcript data
    transcript = result.get("transcript", "")
    video_id = result.get("video_id", "")
    language = result.get("language", "unknown")
    is_auto_generated = result.get("is_auto_generated", False)
    duration_seconds = result.get("duration_seconds", 0)
    segment_count = result.get("segment_count", 0)

    if not transcript:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Empty transcript returned", "url": url}
        )
        return {"success": False, "error": "Empty transcript returned"}

    # Format duration for display
    duration_minutes = int(duration_seconds // 60)
    duration_secs = int(duration_seconds % 60)
    duration_str = f"{duration_minutes}:{duration_secs:02d}"

    # YouTube transcripts don't have logical page boundaries
    # Pass entire content as single page, let token-based chunking handle splits
    pages = [transcript]

    # Calculate token count for metadata
    token_count = count_tokens(transcript)

    # Build metadata for YOUTUBE type
    metadata = {
        "url": url,
        "video_id": video_id,
        "language": language,
        "is_auto_generated": is_auto_generated,
        "duration": duration_str,
        "segment_count": segment_count,
        "character_count": len(transcript),
        "token_count": token_count
    }

    # Use centralized build_processed_output for consistent format
    source_name = source.get("name", f"YouTube: {video_id}")
    processed_content = build_processed_output(
        pages=pages,
        source_type="YOUTUBE",
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
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "Failed to upload processed content to storage"}
        )
        return {"success": False, "error": "Failed to upload processed content to storage"}

    # Update link file with transcript info
    link_data["fetched"] = True
    link_data["fetched_at"] = datetime.now().isoformat()
    link_data["video_id"] = video_id
    link_data["language"] = language
    link_data["is_auto_generated"] = is_auto_generated
    link_data["duration_seconds"] = duration_seconds
    with open(raw_file_path, 'w') as f:
        json.dump(link_data, f, indent=2)

    processing_info = {
        "processor": "youtube_transcript",
        "url": url,
        "video_id": video_id,
        "language": language,
        "is_auto_generated": is_auto_generated,
        "duration": duration_str,
        "duration_seconds": duration_seconds,
        "segment_count": segment_count,
        "character_count": len(transcript),
        "token_count": token_count,
        "total_pages": 1  # Always 1 - token-based chunking handles splits
    }

    # Process embeddings if needed
    source_name = source.get("name", f"YouTube: {video_id}")
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
        active=True,
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
        _, _, reason = needs_embedding(text=processed_text)

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
