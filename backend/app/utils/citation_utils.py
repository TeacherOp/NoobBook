"""
Citation Utilities - Extract content from chunks for citations.

Educational Note: Citations use chunk_ids to reference specific content.
Format: [[cite:CHUNK_ID]] where chunk_id = {source_id}_page_{page}_chunk_{n}

When Claude cites a source with [[cite:chunk_id]], the frontend fetches
the chunk content to display in a tooltip/popover.

Chunk files are stored in Supabase Storage at:
    chunks/{project_id}/{source_id}/{chunk_id}.txt

Each chunk file contains the chunk text content.
"""

import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service


def parse_chunk_id(chunk_id: str) -> Optional[Dict[str, Any]]:
    """
    Parse a chunk_id into its components.

    Educational Note: chunk_id format is {source_id}_page_{page}_chunk_{n}
    Example: abc123-def456_page_5_chunk_2

    Args:
        chunk_id: The chunk ID to parse

    Returns:
        Dict with source_id, page_number, chunk_index, or None if invalid
    """
    # Pattern: {source_id}_page_{page}_chunk_{n}
    # source_id can contain hyphens (UUID format)
    pattern = r'^(.+)_page_(\d+)_chunk_(\d+)$'
    match = re.match(pattern, chunk_id)

    if not match:
        return None

    return {
        "source_id": match.group(1),
        "page_number": int(match.group(2)),
        "chunk_index": int(match.group(3))
    }


def get_chunk_content(
    project_id: str,
    chunk_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get content for a chunk by its chunk_id.

    Educational Note: This is the main function used by the frontend to
    fetch citation content. It downloads the chunk from Supabase Storage
    and returns the text along with metadata for display.

    Args:
        project_id: The project UUID
        chunk_id: The chunk ID (format: {source_id}_page_{page}_chunk_{n})

    Returns:
        Dict with chunk content and metadata, or None if not found:
        {
            "content": "The chunk text...",
            "chunk_id": "abc123_page_5_chunk_2",
            "source_id": "abc123",
            "source_name": "document.pdf",
            "page_number": 5,
            "chunk_index": 2
        }
    """
    # Parse chunk_id to get source_id
    parsed = parse_chunk_id(chunk_id)
    if not parsed:
        return None

    source_id = parsed["source_id"]

    # Download chunk from Supabase Storage
    chunk_text = storage_service.download_chunk(
        project_id=project_id,
        source_id=source_id,
        chunk_id=chunk_id
    )

    if not chunk_text:
        return None

    # Get source name from source index
    source = source_index_service.get_source_from_index(project_id, source_id)
    source_name = source.get("name", "Unknown") if source else "Unknown"

    return {
        "content": chunk_text,
        "chunk_id": chunk_id,
        "source_id": source_id,
        "source_name": source_name,
        "page_number": parsed["page_number"],
        "chunk_index": parsed["chunk_index"]
    }


def get_multiple_chunks(
    project_id: str,
    chunk_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    Get content for multiple chunks at once.

    Educational Note: When a response has multiple citations, the frontend
    can batch-fetch all chunk contents in one call for efficiency.

    Args:
        project_id: The project UUID
        chunk_ids: List of chunk IDs to fetch

    Returns:
        List of chunk content dicts (only includes found chunks)
    """
    results = []

    for chunk_id in chunk_ids:
        chunk_data = get_chunk_content(project_id, chunk_id)
        if chunk_data:
            results.append(chunk_data)

    return results


def extract_citations_from_text(text: str) -> List[str]:
    """
    Extract all chunk_ids from citation markers in text.

    Educational Note: Claude's responses contain citations in format
    [[cite:chunk_id]]. This function extracts all chunk_ids so the
    frontend can fetch their content.

    Args:
        text: Text containing citation markers

    Returns:
        List of unique chunk_ids found in the text
    """
    # Pattern: [[cite:chunk_id]]
    pattern = r'\[\[cite:([^\]]+)\]\]'
    matches = re.findall(pattern, text)

    # Return unique chunk_ids (preserving order)
    seen = set()
    unique = []
    for chunk_id in matches:
        if chunk_id not in seen:
            seen.add(chunk_id)
            unique.append(chunk_id)

    return unique


def get_citations_with_content(
    project_id: str,
    text: str
) -> Dict[str, Dict[str, Any]]:
    """
    Extract citations from text and fetch their content.

    Educational Note: Convenience function that combines extraction and
    fetching. Returns a dict mapping chunk_id -> content for easy lookup.

    Args:
        project_id: The project UUID
        text: Text containing citation markers

    Returns:
        Dict mapping chunk_id to content dict
    """
    chunk_ids = extract_citations_from_text(text)

    result = {}
    for chunk_id in chunk_ids:
        chunk_data = get_chunk_content(project_id, chunk_id)
        if chunk_data:
            result[chunk_id] = chunk_data

    return result
