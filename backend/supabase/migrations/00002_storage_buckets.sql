-- Migration: Storage Buckets Setup
-- Description: Create storage buckets for files and configure policies
-- Created: 2026-01-01

-- ============================================================================
-- STORAGE BUCKETS
-- ============================================================================

-- Bucket for raw uploaded files (PDFs, DOCX, images, audio, etc.)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'raw-files',
  'raw-files',
  false, -- Not public, requires authentication
  104857600, -- 100MB limit
  ARRAY[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', -- DOCX
    'application/vnd.openxmlformats-officedocument.presentationml.presentation', -- PPTX
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
    'audio/mpeg',
    'audio/mp3',
    'audio/wav',
    'audio/m4a',
    'audio/x-m4a',
    'text/plain'
  ]
);

-- Bucket for processed files (extracted text, converted formats)
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES (
  'processed-files',
  'processed-files',
  false,
  104857600 -- 100MB limit
);

-- Bucket for chunk files (optional - can also store in DB)
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES (
  'chunks',
  'chunks',
  false,
  10485760 -- 10MB limit per chunk file
);

-- Bucket for studio outputs (generated audio, images, PDFs, presentations, etc.)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'studio-outputs',
  'studio-outputs',
  false,
  524288000, -- 500MB limit for video files
  ARRAY[
    'audio/mpeg',
    'audio/wav',
    'image/png',
    'image/jpeg',
    'image/svg+xml',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'video/mp4',
    'video/webm',
    'text/html',
    'application/json'
  ]
);

-- ============================================================================
-- STORAGE POLICIES
-- ============================================================================

-- Raw Files Policies
-- Users can upload files to their own projects
CREATE POLICY "Users can upload raw files to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'raw-files' AND
  auth.uid()::text = (storage.foldername(name))[1] -- First folder is user_id
);

-- Users can read files from their own projects
CREATE POLICY "Users can read raw files from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'raw-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can update files in their own projects
CREATE POLICY "Users can update raw files in own projects"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'raw-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Users can delete files from their own projects
CREATE POLICY "Users can delete raw files from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'raw-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Processed Files Policies
CREATE POLICY "Users can upload processed files to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'processed-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can read processed files from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'processed-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can update processed files in own projects"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'processed-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete processed files from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'processed-files' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Chunks Policies
CREATE POLICY "Users can upload chunks to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'chunks' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can read chunks from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'chunks' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete chunks from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'chunks' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- Studio Outputs Policies
CREATE POLICY "Users can upload studio outputs to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'studio-outputs' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can read studio outputs from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'studio-outputs' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can update studio outputs in own projects"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'studio-outputs' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete studio outputs from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'studio-outputs' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

-- ============================================================================
-- STORAGE HELPER FUNCTIONS
-- ============================================================================

-- Function to generate storage path for raw files
CREATE OR REPLACE FUNCTION generate_raw_file_path(
  p_user_id UUID,
  p_project_id UUID,
  p_source_id UUID,
  p_filename TEXT
)
RETURNS TEXT AS $$
BEGIN
  RETURN p_user_id || '/' || p_project_id || '/' || p_source_id || '/' || p_filename;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_raw_file_path IS 'Generate storage path for raw files: {user_id}/{project_id}/{source_id}/{filename}';

-- Function to generate storage path for processed files
CREATE OR REPLACE FUNCTION generate_processed_file_path(
  p_user_id UUID,
  p_project_id UUID,
  p_source_id UUID,
  p_filename TEXT
)
RETURNS TEXT AS $$
BEGIN
  RETURN p_user_id || '/' || p_project_id || '/' || p_source_id || '/' || p_filename;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_processed_file_path IS 'Generate storage path for processed files: {user_id}/{project_id}/{source_id}/{filename}';

-- Function to generate storage path for studio outputs
CREATE OR REPLACE FUNCTION generate_studio_output_path(
  p_user_id UUID,
  p_project_id UUID,
  p_studio_signal_id UUID,
  p_filename TEXT
)
RETURNS TEXT AS $$
BEGIN
  RETURN p_user_id || '/' || p_project_id || '/studio/' || p_studio_signal_id || '/' || p_filename;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_studio_output_path IS 'Generate storage path for studio outputs: {user_id}/{project_id}/studio/{studio_signal_id}/{filename}';
