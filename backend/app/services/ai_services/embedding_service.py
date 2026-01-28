"""
Embedding Service - Orchestrates the full embedding pipeline.

Educational Note: This service coordinates the embedding workflow:
1. Check if source needs embedding (token count > threshold)
2. Parse processed text into chunks (one page = one chunk)
3. Upload chunks to Supabase Storage
4. Create embeddings via OpenAI API
5. Upsert vectors to Pinecone

This service is called after source processing (PDF extraction) completes.
It works for any source type that produces processed text.

Flow:
    Source processed → embedding_service.process_embeddings() →
    → Check tokens → Chunk text → Upload chunks to Supabase → Create embeddings → Upsert to Pinecone
    → Return embedding_info for source metadata

Storage: Chunks are stored in Supabase Storage for retrieval during RAG search.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.utils.embedding_utils import needs_embedding
from app.utils.text import (
    parse_extracted_text,
    chunks_to_pinecone_format,
)
from app.services.integrations.openai import openai_service
from app.services.integrations.pinecone import pinecone_service
from app.services.integrations.supabase import storage_service


class EmbeddingService:
    """
    Service for orchestrating the complete embedding workflow.

    Educational Note: This is a coordinator service that doesn't do
    the actual work - it calls specialized services in the right order
    and handles errors gracefully.
    """

    def __init__(self):
        """Initialize the embedding service."""
        pass

    def process_embeddings(
        self,
        project_id: str,
        source_id: str,
        source_name: str,
        processed_text: str
    ) -> Dict[str, Any]:
        """
        Process embeddings for a source if needed.

        Educational Note: This is the main entry point for the embedding
        workflow. It checks if embedding is needed, and if so, runs the
        full pipeline.

        Storage: Chunks are uploaded to Supabase Storage for retrieval
        during RAG search.

        Args:
            project_id: The project UUID (used as Pinecone namespace)
            source_id: The source UUID
            source_name: Display name of the source (for metadata)
            processed_text: The extracted/processed text content

        Returns:
            Dict with embedding_info:
            {
                "is_embedded": bool,
                "embedded_at": timestamp or None,
                "token_count": int,
                "chunk_count": int or 0,
                "reason": str (explanation of decision)
            }
        """
        # Step 1: Check if embedding is needed
        should_embed, token_count, reason = needs_embedding(
            text=processed_text
        )

        print(f"Embedding check for {source_name}: {reason}")

        if not should_embed:
            return {
                "is_embedded": False,
                "embedded_at": None,
                "token_count": token_count,
                "chunk_count": 0,
                "reason": reason
            }

        # Step 2: Check if Pinecone is configured
        if not pinecone_service.is_configured():
            return {
                "is_embedded": False,
                "embedded_at": None,
                "token_count": token_count,
                "chunk_count": 0,
                "reason": "Pinecone not configured - embedding skipped"
            }

        try:
            # Step 3: Parse text into chunks
            chunks = parse_extracted_text(
                text=processed_text,
                source_id=source_id,
                source_name=source_name
            )

            if not chunks:
                return {
                    "is_embedded": False,
                    "embedded_at": None,
                    "token_count": token_count,
                    "chunk_count": 0,
                    "reason": "No chunks created from text"
                }

            print(f"Created {len(chunks)} chunks for {source_name}")

            # Step 4: Upload chunks to Supabase Storage
            uploaded_count = 0
            for chunk in chunks:
                storage_path = storage_service.upload_chunk(
                    project_id=project_id,
                    source_id=source_id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.text
                )
                if storage_path:
                    uploaded_count += 1
            print(f"Uploaded {uploaded_count} chunks to Supabase Storage")

            # Step 5: Create embeddings for all chunks
            # Educational Note: chunk.text is already cleaned by chunking_service
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = openai_service.create_embeddings_batch(chunk_texts)
            print(f"Created {len(embeddings)} embeddings")

            # Step 6: Convert to Pinecone format and upsert
            vectors = chunks_to_pinecone_format(chunks, embeddings)
            upsert_result = pinecone_service.upsert_vectors(
                vectors=vectors,
                namespace=project_id  # Use project_id as namespace
            )
            print(f"Upserted {upsert_result.get('upserted_count', 0)} vectors to Pinecone")

            return {
                "is_embedded": True,
                "embedded_at": datetime.now().isoformat(),
                "token_count": token_count,
                "chunk_count": len(chunks),
                "reason": f"Successfully embedded {len(chunks)} chunks"
            }

        except Exception as e:
            print(f"Embedding workflow error: {e}")
            return {
                "is_embedded": False,
                "embedded_at": None,
                "token_count": token_count,
                "chunk_count": 0,
                "reason": f"Embedding failed: {str(e)}"
            }

    def delete_embeddings(
        self,
        project_id: str,
        source_id: str
    ) -> Dict[str, Any]:
        """
        Delete embeddings and chunk files for a source.

        Educational Note: When a source is deleted, we need to:
        1. Delete vectors from Pinecone
        2. Delete chunk files from Supabase Storage

        Args:
            project_id: The project UUID (Pinecone namespace)
            source_id: The source UUID

        Returns:
            Dict with deletion results
        """
        results = {
            "pinecone_deleted": False,
            "chunks_deleted": False
        }

        # Delete from Pinecone
        if pinecone_service.is_configured():
            try:
                pinecone_service.delete_by_source(
                    source_id=source_id,
                    namespace=project_id
                )
                results["pinecone_deleted"] = True
                print(f"Deleted vectors for source {source_id} from Pinecone")
            except Exception as e:
                print(f"Error deleting from Pinecone: {e}")

        # Delete chunk files from Supabase Storage
        try:
            storage_service.delete_source_chunks(project_id, source_id)
            results["chunks_deleted"] = True
            print(f"Deleted chunk files from Supabase Storage for source {source_id}")
        except Exception as e:
            print(f"Error deleting chunks from Supabase Storage: {e}")

        return results

    def search_similar(
        self,
        project_id: str,
        query_text: str,
        top_k: int = 5,
        source_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar content using semantic search.

        Educational Note: This is the retrieval part of RAG:
        1. Convert query to embedding
        2. Search Pinecone for similar vectors
        3. Load chunk text from Supabase Storage
        4. Return results with text for AI context

        Args:
            project_id: The project UUID (Pinecone namespace)
            query_text: The user's search query
            top_k: Number of results to return
            source_filter: Optional source_id to filter results

        Returns:
            List of search results with text content
        """
        if not pinecone_service.is_configured():
            return []

        try:
            # Create embedding for query
            query_embedding = openai_service.create_embedding(query_text)

            # Build filter if source specified
            pinecone_filter = None
            if source_filter:
                pinecone_filter = {"source_id": {"$eq": source_filter}}

            # Search Pinecone
            search_results = pinecone_service.search(
                query_vector=query_embedding,
                namespace=project_id,
                top_k=top_k,
                filter=pinecone_filter
            )

            # Enrich results with chunk text from Supabase Storage
            enriched_results = []
            for result in search_results:
                chunk_id = result.get("id")
                source_id = result.get("metadata", {}).get("source_id")

                # Download chunk text from Supabase Storage
                chunk_text = None
                if source_id and chunk_id:
                    chunk_text = storage_service.download_chunk(
                        project_id=project_id,
                        source_id=source_id,
                        chunk_id=chunk_id
                    )

                enriched_result = {
                    "chunk_id": chunk_id,
                    "score": result.get("score"),
                    "source_id": source_id,
                    "source_name": result.get("metadata", {}).get("source_name"),
                    "page_number": result.get("metadata", {}).get("page_number"),
                }

                # Add text from Supabase Storage if found
                if chunk_text:
                    enriched_result["text"] = chunk_text
                else:
                    # Fallback to metadata text (stored in Pinecone)
                    enriched_result["text"] = result.get("metadata", {}).get("text")

                enriched_results.append(enriched_result)

            return enriched_results

        except Exception as e:
            print(f"Search error: {e}")
            return []


# Singleton instance for easy import
embedding_service = EmbeddingService()
