-- Migration: Enable pgvector for embeddings
-- Description: Enable pgvector extension and add embedding column to chunks
-- Created: 2026-01-01

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to chunks table
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index for similarity search (HNSW is faster than IVFFlat for most cases)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks 
USING hnsw (embedding vector_cosine_ops);

-- Function for similarity search
CREATE OR REPLACE FUNCTION search_chunks_by_similarity(
  p_query_embedding vector(1536),
  p_source_ids UUID[],
  p_limit INTEGER DEFAULT 10,
  p_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
  chunk_id TEXT,
  source_id UUID,
  content TEXT,
  page_number INTEGER,
  similarity FLOAT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    c.id as chunk_id,
    c.source_id,
    c.content,
    c.page_number,
    1 - (c.embedding <=> p_query_embedding) as similarity
  FROM chunks c
  WHERE c.source_id = ANY(p_source_ids)
    AND c.embedding IS NOT NULL
    AND 1 - (c.embedding <=> p_query_embedding) >= p_threshold
  ORDER BY c.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_chunks_by_similarity IS 'Search chunks by vector similarity using cosine distance';
