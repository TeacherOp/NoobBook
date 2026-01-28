"""
Supabase Chunk Repository - PostgreSQL-based implementation.

Educational Note: Storing chunks in PostgreSQL enables SQL-based keyword
search alongside Pinecone semantic search. This is more efficient than
file-based storage for hybrid search operations.
"""
from typing import Optional, List, Dict, Any

from app.config.supabase import get_supabase_client
from app.repositories.chunks.interface import ChunkRepositoryInterface


class SupabaseChunkRepository(ChunkRepositoryInterface):
    """Supabase/PostgreSQL implementation of chunk repository."""

    def __init__(self):
        """Initialize with Supabase client."""
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
            if self._client is None:
                raise RuntimeError("Supabase client not available")
        return self._client

    @property
    def table(self):
        """Get the chunks table reference."""
        return self.client.table("chunks")

    # =========================================================================
    # Interface Implementation
    # =========================================================================

    def create(
        self,
        source_id: str,
        project_id: str,
        chunk_id: str,
        text: str,
        page_number: int,
        chunk_number: int,
        token_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new chunk."""
        data = {
            "id": chunk_id,
            "source_id": source_id,
            "project_id": project_id,
            "text": text,
            "page_number": page_number,
            "chunk_number": chunk_number,
            "token_count": token_count
        }

        result = self.table.insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create chunk")

        return result.data[0]

    def create_batch(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Create multiple chunks in batch.

        Educational Note: Supabase supports batch inserts for efficiency.
        """
        if not chunks:
            return 0

        # Format chunks for insertion
        data = [
            {
                "id": c["id"],
                "source_id": c["source_id"],
                "project_id": c["project_id"],
                "text": c["text"],
                "page_number": c["page_number"],
                "chunk_number": c["chunk_number"],
                "token_count": c.get("token_count")
            }
            for c in chunks
        ]

        result = self.table.insert(data).execute()
        return len(result.data) if result.data else 0

    def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a chunk by its ID."""
        result = self.table.select("*").eq("id", chunk_id).execute()

        if not result.data:
            return None
        return result.data[0]

    def get_by_source(self, source_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a source."""
        result = self.table.select("*").eq(
            "source_id", source_id
        ).order("page_number").order("chunk_number").execute()

        return result.data

    def get_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a project."""
        result = self.table.select("*").eq("project_id", project_id).execute()
        return result.data

    def delete_by_source(self, source_id: str) -> int:
        """Delete all chunks for a source."""
        result = self.table.delete().eq("source_id", source_id).execute()
        return len(result.data) if result.data else 0

    def delete_by_project(self, project_id: str) -> int:
        """Delete all chunks for a project."""
        result = self.table.delete().eq("project_id", project_id).execute()
        return len(result.data) if result.data else 0

    def search_by_keywords(
        self,
        source_id: str,
        keywords: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search chunks by keywords using PostgreSQL full-text search.

        Educational Note: PostgreSQL provides built-in full-text search
        via tsvector/tsquery. The chunks table has a gin index on the
        text column for efficient searching.
        """
        if not keywords:
            # Return first N chunks if no keywords
            result = self.table.select("*").eq(
                "source_id", source_id
            ).limit(limit).execute()
            return result.data

        # Build search query
        # Convert keywords to tsquery format: word1 | word2 | word3
        query_str = ' | '.join(keywords)

        try:
            # Use PostgreSQL full-text search
            # Note: This requires the text_search index created in schema.sql
            result = self.client.rpc(
                "search_chunks_by_keywords",
                {
                    "p_source_id": source_id,
                    "p_query": query_str,
                    "p_limit": limit
                }
            ).execute()

            return result.data if result.data else []
        except Exception as e:
            # Fallback to simple ILIKE search
            print(f"Full-text search failed, using fallback: {e}")
            return self._search_fallback(source_id, keywords, limit)

    def _search_fallback(
        self,
        source_id: str,
        keywords: List[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback keyword search using ILIKE.

        Educational Note: If the PostgreSQL function isn't available,
        we fall back to basic pattern matching.
        """
        results = []
        seen_ids = set()

        for keyword in keywords:
            # Search for each keyword
            result = self.table.select("*").eq(
                "source_id", source_id
            ).ilike("text", f"%{keyword}%").limit(limit).execute()

            for chunk in result.data:
                if chunk["id"] not in seen_ids:
                    chunk["relevance_score"] = 1.0  # Simple binary relevance
                    results.append(chunk)
                    seen_ids.add(chunk["id"])

        return results[:limit]

    def get_chunk_count(self, source_id: str) -> int:
        """Get the number of chunks for a source."""
        result = self.table.select("id", count="exact").eq("source_id", source_id).execute()
        return result.count if result.count else 0
