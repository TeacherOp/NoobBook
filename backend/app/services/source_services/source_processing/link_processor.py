"""
Link Processor - Handles website URL processing.

Educational Note: Link sources are stored as .link files containing JSON
with the URL and metadata. We use the web_agent_service to fetch and
extract content from the URL.

The web agent:
1. Tries Claude's web_fetch first
2. Falls back to Tavily search if web_fetch fails
3. Returns structured content via return_search_result tool

Storage: Processed content is stored in Supabase Storage. Chunks are also
stored in Supabase Storage for RAG retrieval.
"""
import json
from pathlib import Path
from typing import Dict, Any

from app.utils.text import build_processed_output
from app.utils.embedding_utils import needs_embedding, count_tokens
from app.services.integrations.supabase import storage_service
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service


def process_link(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process a link source - extract content from URL using web agent.

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the .link file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    from app.services.ai_agents import web_agent_service
    from app.services.source_services.source_processing.youtube_processor import process_youtube

    # Read the .link file to get URL
    with open(raw_file_path, 'r') as f:
        link_data = json.load(f)

    url = link_data.get("url")
    link_type = link_data.get("type", "website")

    if not url:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "No URL found in link file"}
        )
        return {"success": False, "error": "No URL found in link file"}

    # Handle YouTube videos separately
    if link_type == "youtube":
        return process_youtube(
            project_id, source_id, source, url, link_data, raw_file_path, source_service
        )

    print(f"Processing link source: {url}")

    # Use web agent to extract content
    result = web_agent_service.run(
        url=url,
        project_id=project_id,
        source_id=source_id
    )

    if not result.get("success"):
        error_msg = result.get("error_message", "Failed to extract content from URL")
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={
                "error": error_msg,
                "url": url,
                "iterations": result.get("iterations"),
                "usage": result.get("usage")
            }
        )
        return {"success": False, "error": error_msg}

    # Extract content from agent result
    content = result.get("content", "")
    title = result.get("title", url)
    summary = result.get("summary", "")
    content_type = result.get("content_type", "other")
    source_urls = result.get("source_urls", [url])

    if not content:
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={"error": "No content extracted from URL", "url": url}
        )
        return {"success": False, "error": "No content extracted from URL"}

    # Links don't have logical page boundaries
    # Pass entire content as single page, let token-based chunking handle splits
    pages = [content]

    # Calculate token count for metadata
    token_count = count_tokens(content)

    # Build metadata for LINK type
    metadata = {
        "url": url,
        "title": title,
        "content_type": content_type,
        "character_count": len(content),
        "token_count": token_count
    }

    # Use centralized build_processed_output for consistent format
    source_name = source.get("name", url)
    processed_content = build_processed_output(
        pages=pages,
        source_type="LINK",
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

    # Update link file to mark as fetched
    link_data["fetched"] = True
    link_data["fetched_at"] = result.get("extracted_at")
    link_data["title"] = title
    link_data["content_type"] = content_type
    with open(raw_file_path, 'w') as f:
        json.dump(link_data, f, indent=2)

    processing_info = {
        "processor": "web_agent",
        "url": url,
        "title": title,
        "content_type": content_type,
        "character_count": len(content),
        "total_pages": 1,  # Links are always single-page (chunking handles splits)
        "source_urls": source_urls,
        "iterations": result.get("iterations"),
        "usage": result.get("usage"),
        "extracted_at": result.get("extracted_at")
    }

    # Process embeddings if needed
    source_name = source.get("name", url)
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
