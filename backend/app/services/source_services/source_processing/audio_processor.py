"""
Audio Processor - Handles audio file processing.

Educational Note: Audio files are transcribed using ElevenLabs' Scribe v1
model, which provides high-accuracy transcription with optional speaker
diarization and audio event detection.

Storage: Processed content is stored in Supabase Storage. Chunks are also
stored in Supabase Storage for RAG retrieval.
"""
from pathlib import Path
from typing import Dict, Any

from app.services.integrations.supabase import storage_service
from app.utils.embedding_utils import needs_embedding
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service


def process_audio(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process an audio file - transcribe using ElevenLabs Speech-to-Text.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the raw audio file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    from app.services.integrations.elevenlabs import audio_service

    # Check if ElevenLabs is configured
    if not audio_service.is_configured():
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "ELEVENLABS_API_KEY not configured. Please add it in App Settings."}
        )
        return {"success": False, "error": "ELEVENLABS_API_KEY not configured"}

    # Transcribe the audio file
    result = audio_service.transcribe_audio(
        project_id=project_id,
        source_id=source_id,
        audio_path=raw_file_path
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
            "processor": "audio_service",
            "model_used": result.get("model_used"),
            "character_count": result.get("character_count"),
            "token_count": result.get("token_count"),
            "detected_language_code": result.get("detected_language_code"),
            "detected_language_name": result.get("detected_language_name"),
            "diarization_enabled": result.get("diarization_enabled"),
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
