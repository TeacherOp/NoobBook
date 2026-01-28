"""
Chunk Repository Interface - Contract for chunk data access.

Educational Note: Chunks are segments of processed source text used for RAG.
They're stored with page/chunk numbers for precise citation references.
The chunk ID format is: {source_id}_page_{N}_chunk_{M}
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class ChunkRepositoryInterface(ABC):
    """Interface for chunk repository operations."""

    @abstractmethod
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
        """
        Create a new chunk.

        Args:
            source_id: The source UUID
            project_id: The project UUID
            chunk_id: The chunk ID ({source_id}_page_{N}_chunk_{M})
            text: The chunk text content
            page_number: Page number in source
            chunk_number: Chunk number within page
            token_count: Optional token count

        Returns:
            Created chunk record
        """
        raise NotImplementedError

    @abstractmethod
    def create_batch(
        self,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Create multiple chunks in batch.

        Args:
            chunks: List of chunk dicts with required fields

        Returns:
            Number of chunks created
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a chunk by its ID.

        Args:
            chunk_id: The chunk ID

        Returns:
            Chunk record or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_source(self, source_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a source.

        Args:
            source_id: The source UUID

        Returns:
            List of chunks ordered by page_number, chunk_number
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a project.

        Args:
            project_id: The project UUID

        Returns:
            List of chunks
        """
        raise NotImplementedError

    @abstractmethod
    def delete_by_source(self, source_id: str) -> int:
        """
        Delete all chunks for a source.

        Args:
            source_id: The source UUID

        Returns:
            Number of chunks deleted
        """
        raise NotImplementedError

    @abstractmethod
    def delete_by_project(self, project_id: str) -> int:
        """
        Delete all chunks for a project.

        Args:
            project_id: The project UUID

        Returns:
            Number of chunks deleted
        """
        raise NotImplementedError

    @abstractmethod
    def search_by_keywords(
        self,
        source_id: str,
        keywords: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search chunks by keywords (fuzzy matching).

        Educational Note: This is the local keyword search component
        of hybrid search. Used alongside Pinecone semantic search.

        Args:
            source_id: The source UUID
            keywords: List of keywords to search for
            limit: Maximum results to return

        Returns:
            List of matching chunks with relevance scores
        """
        raise NotImplementedError

    @abstractmethod
    def get_chunk_count(self, source_id: str) -> int:
        """
        Get the number of chunks for a source.

        Args:
            source_id: The source UUID

        Returns:
            Chunk count
        """
        raise NotImplementedError
