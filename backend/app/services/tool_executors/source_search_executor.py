"""
Source Search Executor - Executes source search tool calls with hybrid search.

Educational Note: This service implements a smart search strategy:
1. Small sources (<1000 tokens): Return ALL chunks (no search needed)
2. Large sources (>=1000 tokens): Hybrid search
   - Local keyword search: Fast text matching with fuzzy support
   - Semantic search: Pinecone vector similarity
   - Results are combined and deduped by chunk_id

The executor returns chunk_ids that Claude uses for citations.
Citation format: [[cite:CHUNK_ID]] where CHUNK_ID = {source_id}_page_{page}_chunk_{n}
"""
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher

from app.services.source_services import source_service
from app.services.integrations.openai import openai_service
from app.services.integrations.pinecone import pinecone_service
from app.services.integrations.supabase import storage_service


class SourceSearchExecutor:
    """
    Executor for source search tool calls with hybrid search capability.

    Educational Note: This class implements two search strategies:
    1. Small sources: Return all chunks (efficient for <1000 tokens)
    2. Large sources: Hybrid search combining:
       - Local keyword matching (fast, exact + fuzzy)
       - Semantic search via Pinecone (conceptual similarity)
    """

    # Token threshold for "small" sources - return all chunks without search
    SMALL_SOURCE_THRESHOLD = 1000

    # Number of results to return from each search method
    DEFAULT_TOP_K = 5

    # Fuzzy matching threshold (0.0 to 1.0, higher = stricter)
    FUZZY_THRESHOLD = 0.7

    def __init__(self):
        """Initialize the executor."""
        pass

    def execute(
        self,
        project_id: str,
        source_id: str,
        keywords: Optional[List[str]] = None,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a source search with smart strategy based on source size.

        Educational Note: The search strategy adapts to source size:
        - Small sources (<1000 tokens): Return all chunks immediately
        - Large sources: Use keywords for text matching and/or query for semantic search

        Args:
            project_id: The project UUID
            source_id: The source UUID to search
            keywords: Optional list of keywords for text matching (1-2 words each)
            query: Optional semantic search query phrase

        Returns:
            Dict with search results including chunk_ids for citations
        """
        # Get source metadata
        source = source_service.get_source(project_id, source_id)

        if not source:
            return {
                "success": False,
                "error": f"Source not found: {source_id}"
            }

        # Check if source is ready and active
        if source.get("status") != "ready":
            return {
                "success": False,
                "error": f"Source is not ready (status: {source.get('status')})"
            }

        if not source.get("active", False):
            return {
                "success": False,
                "error": "Source is not active"
            }

        # Get token count from embedding_info
        embedding_info = source.get("embedding_info", {})
        token_count = embedding_info.get("token_count", 0)

        # Decision: small source = return all, large source = search
        if token_count < self.SMALL_SOURCE_THRESHOLD:
            return self._get_all_chunks(project_id, source_id, source)
        else:
            return self._search_large_source(
                project_id, source_id, source, keywords, query
            )

    def _get_all_chunks(
        self,
        project_id: str,
        source_id: str,
        source: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Return all chunks for a small source.

        Educational Note: For small sources, it's more efficient to return
        everything rather than search. Claude can process all chunks and
        find the relevant information itself.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            source: Source metadata dict

        Returns:
            Dict with all chunks and their chunk_ids
        """
        # Load chunks from Supabase Storage
        all_chunks = storage_service.list_source_chunks(project_id, source_id)

        if not all_chunks:
            return {
                "success": False,
                "error": "No chunks found for this source"
            }

        # Format all chunks with their chunk_ids
        formatted = self._format_chunks(all_chunks, source)

        return {
            "success": True,
            "source_name": source.get("name", "Unknown"),
            "source_id": source_id,
            "content": formatted,
            "search_type": "full_content",
            "chunk_count": len(all_chunks)
        }

    def _search_large_source(
        self,
        project_id: str,
        source_id: str,
        source: Dict[str, Any],
        keywords: Optional[List[str]],
        query: Optional[str]
    ) -> Dict[str, Any]:
        """
        Search a large source using hybrid search (keywords + semantic).

        Educational Note: For large sources, we combine two search strategies:
        1. Keyword search: Fast local text matching for specific terms
        2. Semantic search: Vector similarity for conceptual relevance
        Results are combined and deduped by chunk_id.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            source: Source metadata dict
            keywords: Optional keywords for text matching
            query: Optional semantic search query

        Returns:
            Dict with matching chunks and their chunk_ids
        """
        results = []

        # Load all chunks from Supabase Storage for local search
        all_chunks = storage_service.list_source_chunks(project_id, source_id)

        if not all_chunks:
            return {
                "success": False,
                "error": "No chunks found for this source"
            }

        # Local keyword search
        if keywords:
            keyword_results = self._local_keyword_search(all_chunks, keywords)
            results.extend(keyword_results)

        # Semantic search via Pinecone
        if query:
            semantic_results = self._semantic_search(
                project_id, source_id, query
            )
            results.extend(semantic_results)

        # If no search params provided, return top chunks
        if not keywords and not query:
            # Return first few chunks as fallback
            results = all_chunks[:self.DEFAULT_TOP_K]

        # Dedupe by chunk_id
        deduped = self._dedupe_results(results)

        if not deduped:
            return {
                "success": True,
                "source_name": source.get("name", "Unknown"),
                "source_id": source_id,
                "content": "No matching content found.",
                "search_type": "hybrid_search",
                "matches": 0
            }

        # Format results
        formatted = self._format_chunks(deduped, source)

        return {
            "success": True,
            "source_name": source.get("name", "Unknown"),
            "source_id": source_id,
            "content": formatted,
            "search_type": "hybrid_search",
            "matches": len(deduped)
        }

    def _local_keyword_search(
        self,
        chunks: List[Dict[str, Any]],
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Perform local keyword search with fuzzy matching.

        Educational Note: This search is fast because it operates on local
        chunk files (max ~1000 files, each <500 chars). We use:
        - Case-insensitive exact matching
        - Fuzzy matching via difflib for typo tolerance
        - Scoring by keyword frequency

        Args:
            chunks: List of chunk dicts (from load_chunks_for_source)
            keywords: List of keywords to search for

        Returns:
            List of matching chunks sorted by relevance score
        """
        scored_chunks = []

        for chunk in chunks:
            text = chunk.get("text", "").lower()
            score = 0

            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Exact match (case-insensitive)
                if keyword_lower in text:
                    # Count occurrences for scoring
                    score += text.count(keyword_lower) * 2
                else:
                    # Fuzzy match - check each word in text
                    words = text.split()
                    for word in words:
                        # Clean word of punctuation
                        clean_word = ''.join(c for c in word if c.isalnum())
                        if clean_word:
                            similarity = SequenceMatcher(
                                None, keyword_lower, clean_word
                            ).ratio()
                            if similarity >= self.FUZZY_THRESHOLD:
                                score += similarity

            if score > 0:
                # Add score to chunk for sorting
                chunk_with_score = chunk.copy()
                chunk_with_score["_search_score"] = score
                scored_chunks.append(chunk_with_score)

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x.get("_search_score", 0), reverse=True)

        # Return top results
        return scored_chunks[:self.DEFAULT_TOP_K]

    def _semantic_search(
        self,
        project_id: str,
        source_id: str,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search via Pinecone.

        Educational Note: Semantic search finds conceptually similar content
        even if the exact words don't match. It works by:
        1. Converting query to embedding vector
        2. Finding similar vectors in Pinecone
        3. Returning chunks with their metadata

        Args:
            project_id: The project UUID
            source_id: The source UUID
            query: Search query phrase

        Returns:
            List of matching chunks from Pinecone
        """
        try:
            # Check if Pinecone is configured
            if not pinecone_service.is_configured():
                print("Pinecone not configured, skipping semantic search")
                return []

            # Create query embedding
            query_vector = openai_service.create_embedding(query)

            # Search Pinecone with source_id filter
            results = pinecone_service.search(
                query_vector=query_vector,
                namespace=project_id,
                top_k=self.DEFAULT_TOP_K,
                filter={"source_id": {"$eq": source_id}},
                include_metadata=True
            )

            if not results:
                return []

            # Convert Pinecone results to chunk format
            chunks = []
            for result in results:
                metadata = result.get("metadata", {})
                chunks.append({
                    "chunk_id": result.get("id"),
                    "text": metadata.get("text", ""),
                    "page_number": metadata.get("page_number", 1),
                    "source_id": metadata.get("source_id", source_id),
                    "source_name": metadata.get("source_name", ""),
                    "_search_score": result.get("score", 0)
                })

            return chunks

        except Exception as e:
            print(f"Semantic search failed: {e}")
            return []

    def _dedupe_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Dedupe results by chunk_id, keeping highest scored version.

        Educational Note: When combining keyword and semantic search results,
        the same chunk might appear in both. We keep only one instance,
        preferring the one with the higher search score.

        Args:
            results: List of chunk dicts (may have duplicates)

        Returns:
            Deduped list of chunks
        """
        seen = {}

        for chunk in results:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                continue

            score = chunk.get("_search_score", 0)

            if chunk_id not in seen or score > seen[chunk_id].get("_search_score", 0):
                seen[chunk_id] = chunk

        # Return sorted by score
        deduped = list(seen.values())
        deduped.sort(key=lambda x: x.get("_search_score", 0), reverse=True)

        return deduped

    def _format_chunks(
        self,
        chunks: List[Dict[str, Any]],
        source: Dict[str, Any]
    ) -> str:
        """
        Format chunks for Claude's consumption with chunk_ids for citation.

        Educational Note: The formatted output includes chunk_ids that Claude
        uses for citations. Format: [[cite:CHUNK_ID]] where chunk_id contains
        source, page, and chunk info.

        Args:
            chunks: List of chunk dicts
            source: Source metadata

        Returns:
            Formatted string with chunks and citation info
        """
        lines = [
            f"## Content from: {source.get('name', 'Unknown')}",
            f"Found {len(chunks)} relevant section(s).",
            "",
            "Use the chunk_id in citations: [[cite:chunk_id]]",
            ""
        ]

        for i, chunk in enumerate(chunks, 1):
            chunk_id = chunk.get("chunk_id", "unknown")
            page = chunk.get("page_number", "?")
            text = chunk.get("text", "")
            score = chunk.get("_search_score")

            lines.append(f"### Section {i}")
            lines.append(f"**chunk_id:** {chunk_id}")
            lines.append(f"**Page:** {page}")
            if score is not None:
                lines.append(f"**Relevance:** {score:.2f}")
            lines.append("")
            lines.append(text)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)


# Singleton instance
source_search_executor = SourceSearchExecutor()
