-- NoobBook Storage Buckets Migration
-- Run this in Supabase SQL Editor to create storage buckets
-- Created: 2026-01-04

-- ============================================================================
-- STORAGE BUCKETS
-- ============================================================================
-- Educational Note: Supabase Storage uses buckets to organize files.
-- Each bucket can have its own access policies.

-- Raw files bucket (PDFs, images, audio, etc.)
INSERT INTO storage.buckets (id, name, public)
VALUES ('raw-files', 'raw-files', false)
ON CONFLICT (id) DO NOTHING;

-- Processed files bucket (extracted text)
INSERT INTO storage.buckets (id, name, public)
VALUES ('processed-files', 'processed-files', false)
ON CONFLICT (id) DO NOTHING;

-- Chunks bucket (text chunks for RAG)
INSERT INTO storage.buckets (id, name, public)
VALUES ('chunks', 'chunks', false)
ON CONFLICT (id) DO NOTHING;

-- Studio outputs bucket (generated content)
INSERT INTO storage.buckets (id, name, public)
VALUES ('studio-outputs', 'studio-outputs', false)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STORAGE POLICIES (Allow all for single-user mode)
-- ============================================================================
-- Educational Note: For single-user self-hosted mode, we allow all operations.
-- In multi-user mode, you'd add RLS policies based on user_id.

-- Raw files policies
CREATE POLICY "Allow all operations on raw-files"
ON storage.objects FOR ALL
USING (bucket_id = 'raw-files')
WITH CHECK (bucket_id = 'raw-files');

-- Processed files policies
CREATE POLICY "Allow all operations on processed-files"
ON storage.objects FOR ALL
USING (bucket_id = 'processed-files')
WITH CHECK (bucket_id = 'processed-files');

-- Chunks policies
CREATE POLICY "Allow all operations on chunks"
ON storage.objects FOR ALL
USING (bucket_id = 'chunks')
WITH CHECK (bucket_id = 'chunks');

-- Studio outputs policies
CREATE POLICY "Allow all operations on studio-outputs"
ON storage.objects FOR ALL
USING (bucket_id = 'studio-outputs')
WITH CHECK (bucket_id = 'studio-outputs');

-- ============================================================================
-- DONE!
-- ============================================================================
-- Storage buckets created:
-- - raw-files: Original uploaded files (PDFs, images, audio)
-- - processed-files: Extracted text content
-- - chunks: Text chunks for RAG search
-- - studio-outputs: Generated content (audio, video, documents)
