"""
Source Content Utilities - Shared functions for loading source content.

Used by multiple agents (blog, website, etc.) to get source content
with smart sampling for large sources.
"""

from typing import Optional, List
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service


def get_sampled_source_content(
    project_id: str,
    source_id: str,
    max_tokens: int = 10000,
    max_chunks: int = 20
) -> str:
    """
    Get source content for AI processing with smart sampling.

    For small sources (token_count < max_tokens): returns full content.
    For large sources: samples chunks evenly distributed.

    Args:
        project_id: Project ID
        source_id: Source ID
        max_tokens: Max tokens before sampling (approx)
        max_chunks: Max chunks to sample for large sources

    Returns:
        Source content string
    """
    try:
        # Get source metadata
        source = source_index_service.get_source_from_index(project_id, source_id)
        if not source:
            return "Error: Source not found"

        # Check existing token count if available
        embedding_info = source.get("embedding_info", {}) or {}
        token_count = embedding_info.get("token_count", 0) or 0
        
        # approximate chars from tokens if needed, but we rely on storage logic
        
        # 1. Try to get full processed content if small enough
        if token_count < max_tokens:
            processed_content = storage_service.download_processed_file(project_id, source_id)
            if processed_content:
                return processed_content
                
        # 2. If large or processed download failed, try chunks
        chunk_ids = storage_service.list_source_chunk_ids(project_id, source_id)
        
        if not chunk_ids:
            # Fallback to processed file if no chunks (maybe just on the boundary or token count missing)
            processed_content = storage_service.download_processed_file(project_id, source_id)
            if processed_content:
                 # Truncate if really too long? 
                 # For now, just return it, trusting caller or max_tokens check wasn't way off
                 # Or we can do a hard truncate if strictly required.
                 return processed_content
            return ""

        # Smart Sampling
        total_chunks = len(chunk_ids)
        
        if total_chunks <= max_chunks:
            selected_ids = chunk_ids
        else:
            # Sample evenly
            step = max(1, total_chunks // max_chunks)
            selected_ids = []
            for i in range(0, total_chunks, step):
                if len(selected_ids) >= max_chunks:
                    break
                selected_ids.append(chunk_ids[i])
                
        # Download selected chunks
        content_parts = []
        for cid in selected_ids:
            chunk_text = storage_service.download_chunk(project_id, source_id, cid)
            if chunk_text:
                content_parts.append(chunk_text.strip())
                
        return "\n\n---\n\n".join(content_parts)

    except Exception as e:
        print(f"Error loading source content: {e}")
        return f"Error loading source content: {str(e)}"

# Alias for backward compatibility, mapping approx chars to tokens
def get_source_content(
    project_id: str,
    source_id: str,
    max_chars: int = 15000,
    max_chunks: int = 12
) -> str:
    """Wrapper for get_sampled_source_content to maintain backward compatibility."""
    # Approx 4 chars per token -> 15000 chars ~ 3750 tokens
    max_tokens = max_chars // 4
    return get_sampled_source_content(
        project_id, 
        source_id, 
        max_tokens=max_tokens, 
        max_chunks=max_chunks
    )


def get_source_name(project_id: str, source_id: str) -> Optional[str]:
    """Get source name by ID."""
    try:
        source = source_index_service.get_source_from_index(project_id, source_id)
        return source.get("name") if source else None
    except Exception:
        return None
