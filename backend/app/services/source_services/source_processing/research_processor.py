"""
Research Processor - Handles deep research source processing.

Educational Note: This processor orchestrates an AI agent that:
1. Reads the research request (.research JSON file)
2. Uses web search to find relevant information
3. Fetches and analyzes provided reference links
4. Synthesizes findings into a comprehensive document
5. Saves the result for embedding and chat context

Storage: Processed content is stored in Supabase Storage. Chunks are also
stored in Supabase Storage for RAG retrieval.
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.utils.text import build_processed_output
from app.utils.embedding_utils import needs_embedding, count_tokens
from app.services.integrations.supabase import storage_service
from app.services.ai_services.embedding_service import embedding_service
from app.services.ai_services.summary_service import summary_service


def process_research(
    project_id: str,
    source_id: str,
    source: Dict[str, Any],
    raw_file_path: Path,
    source_service
) -> Dict[str, Any]:
    """
    Process a research source by running the deep research agent.

    Educational Note: This is a long-running process that:
    1. Loads the research request parameters
    2. Runs an AI agent with web search capabilities
    3. Compiles findings into a structured document
    4. Embeds the content for RAG retrieval

    Args:
        project_id: The project UUID
        source_id: The source UUID
        source: Source metadata dict
        raw_file_path: Path to the .research JSON file
        source_service: Reference to source_service for updates

    Returns:
        Dict with success status
    """
    # Load research request
    with open(raw_file_path, "r", encoding="utf-8") as f:
        research_request = json.load(f)

    topic = research_request.get("topic", "Unknown Topic")
    description = research_request.get("description", "")
    links = research_request.get("links", [])

    source_name = source.get("name", topic)

    print(f"Starting deep research for: {topic}")
    print(f"Description: {description[:100]}...")
    print(f"Reference links: {len(links)}")

    # Use temp file for agent output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        # Run the deep research agent
        # Agent writes directly to temp file via executor
        from app.services.ai_agents.deep_research_agent import deep_research_agent

        research_result = deep_research_agent.research(
            project_id=project_id,
            source_id=source_id,
            topic=topic,
            description=description,
            links=links,
            output_path=str(temp_path)
        )

        if not research_result.get("success"):
            raise Exception(research_result.get("error", "Research failed"))

        # Read the content that the agent wrote to file
        if not temp_path.exists():
            raise Exception("Research agent did not create output file")

        with open(temp_path, "r", encoding="utf-8") as f:
            research_content = f.read()

        if not research_content:
            raise Exception("Research agent wrote empty content")

        segments_written = research_result.get("segments_written", 0)
        iterations = research_result.get("iterations", 0)
        print(f"Research complete: {len(research_content)} chars, {segments_written} segments, {iterations} iterations")

    except Exception as e:
        print(f"Research agent error: {e}")
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
        source_service.update_source(
            project_id,
            source_id,
            status="error",
            processing_info={
                "error": str(e),
                "processor": "research_processor"
            }
        )
        return {"success": False, "error": str(e)}
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()

    # Calculate token count for metadata
    token_count = count_tokens(research_content)

    # Build metadata for RESEARCH type
    metadata = {
        "topic": topic,
        "link_count": len(links),
        "character_count": len(research_content),
        "token_count": token_count
    }

    # Use centralized build_processed_output for consistent format
    # Research output is treated as a single "page" document
    processed_content = build_processed_output(
        pages=[research_content],
        source_type="RESEARCH",
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

    processing_info = {
        "processor": "research_processor",
        "topic": topic,
        "link_count": len(links),
        "character_count": len(research_content),
        "token_count": token_count,
        "total_pages": 1,
        "segments_written": segments_written,
        "iterations": iterations,
        "researched_at": datetime.now().isoformat()
    }

    # Process embeddings
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

    print(f"Research source ready: {source_name}")
    return {"success": True, "status": "ready"}


def _process_embeddings(
    project_id: str,
    source_id: str,
    source_name: str,
    processed_text: str,
    source_service
) -> Dict[str, Any]:
    """
    Process embeddings for a research source.

    Educational Note: Research documents are typically comprehensive and
    benefit greatly from semantic search via embeddings.
    Chunks are uploaded to Supabase Storage.
    """
    try:
        # Get embedding info
        _, token_count, reason = needs_embedding(text=processed_text)

        # Update status to "embedding" before starting
        source_service.update_source(project_id, source_id, status="embedding")
        print(f"Starting embedding for research: {source_name} ({reason})")

        # Process embeddings using the embedding service
        # Chunks are automatically uploaded to Supabase Storage
        return embedding_service.process_embeddings(
            project_id=project_id,
            source_id=source_id,
            source_name=source_name,
            processed_text=processed_text
        )

    except Exception as e:
        print(f"Error processing embeddings for research {source_id}: {e}")
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
    """Generate a summary for a processed research source."""
    try:
        print(f"Generating summary for research source: {source_id}")
        result = summary_service.generate_summary(
            project_id=project_id,
            source_id=source_id,
            source_metadata=source_metadata
        )
        if result:
            print(f"Summary generated for research {source_id}: {len(result.get('summary', ''))} chars")
            return result
        return {}
    except Exception as e:
        print(f"Error generating summary for research {source_id}: {e}")
        return {}
