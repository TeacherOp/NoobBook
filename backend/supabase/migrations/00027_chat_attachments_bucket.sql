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
-- Mirrors the raw-files / brand-assets pattern intentionally. Important
-- nuance: the path layout we actually upload is
--   {project_id}/{chat_id}/{attachment_id}/{filename}
-- so `(storage.foldername(name))[1]` resolves to project_id, NOT user_id.
-- The `auth.uid()::text = first_folder` check below therefore *cannot*
-- match for user-token access — by design.
--
-- This is consistent with the existing buckets (raw-files in
-- 00002_storage_buckets.sql, brand-assets in 00007_brand_assets.sql)
-- which have the same shape. The backend always reads/writes with the
-- service key (bypassing RLS) and hands the browser short-lived signed
-- URLs that don't go through these policies. Direct user-token uploads
-- aren't a feature today; if/when that lands, swap the path prefix to
-- {user_id}/{project_id}/{chat_id}/... so this policy actually grants
-- access (matching the convention encoded in
-- generate_raw_file_path / generate_brand_asset_path).

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
