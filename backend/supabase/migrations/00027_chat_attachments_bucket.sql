-- Migration: Chat Attachments Storage Bucket
-- Description: Bucket + storage policies for inline images pasted/dropped
--              into the chat input (screenshots, etc.). Distinct from
--              raw-files because the lifecycle is per-chat (cascade-delete
--              on chat removal) rather than per-source.
-- Created: 2026-05-08

-- ============================================================================
-- STORAGE BUCKET
-- ============================================================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'chat-attachments',
  'chat-attachments',
  false, -- Private; access via signed URLs
  10485760, -- 10MB per attachment (Claude vision caps at 5MB; 2× headroom for transient pre-validation)
  ARRAY[
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
    'image/gif'
  ]
);

-- ============================================================================
-- STORAGE POLICIES
-- ============================================================================
-- Mirrors the raw-files / brand-assets pattern. Backend uploads/reads using
-- the service key (bypasses RLS); these policies are for direct user-token
-- access (e.g., a future feature that lets the frontend upload directly).

CREATE POLICY "Users can upload chat attachments to own projects"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can read chat attachments from own projects"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can update chat attachments in own projects"
ON storage.objects FOR UPDATE
USING (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete chat attachments from own projects"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'chat-attachments' AND
  auth.uid()::text = (storage.foldername(name))[1]
);
