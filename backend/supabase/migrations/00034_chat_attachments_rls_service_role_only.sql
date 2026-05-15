-- Migration: Chat attachments RLS — scope to service_role only
-- Created: 2026-05-14
--
-- Context: 00032 installed a permissive policy with no `TO` filter on the
-- chat-attachments bucket to unblock uploads after several failed
-- ownership-predicate attempts (00027 / 00028 / 00030). The
-- comment block in 00032 argued residual risk was bucket-spam only
-- because "signed URLs are still required to actually read someone
-- else's attachment".
--
-- That claim turns out to be wrong: storage-api applies the bucket RLS
-- to direct authenticated `GET /storage/v1/object/chat-attachments/...`
-- calls. A user with any valid JWT (their own) can read / write / delete
-- / enumerate every chat attachment in every project by talking to
-- storage-api directly, bypassing the backend's project-access RBAC.
--
-- Tightening shape: scope the policy `TO service_role` only. The
-- backend already runs as service_role for all storage writes, and the
-- browser reads attachments via signed URLs (storage-api validates the
-- signature cryptographically and bypasses RLS via that path — see
-- supabase/storage-api `getSignedURL` → `signedUrl` verifier).
--
-- Net effect:
--   1. Backend (service_role JWT) — unchanged, can read/write all rows.
--   2. Browser via signed URLs — unchanged, signature bypasses RLS.
--   3. Authenticated user direct-SDK call with own JWT — now 403,
--      which is the intended posture.

DROP POLICY IF EXISTS "Chat attachments — backend & signed-url access" ON storage.objects;

CREATE POLICY "chat_attachments_service_role_only"
ON storage.objects
FOR ALL
TO service_role
USING (bucket_id = 'chat-attachments')
WITH CHECK (bucket_id = 'chat-attachments');

-- Audit: confirm no stray `authenticated`-scoped policy overlaps for
-- this bucket. If one slipped in via a future migration that bypassed
-- review, fail loudly here instead of regressing the fix.
DO $$
DECLARE
  overlap_count integer;
BEGIN
  SELECT COUNT(*) INTO overlap_count
  FROM pg_policies
  WHERE schemaname = 'storage'
    AND tablename = 'objects'
    AND policyname <> 'chat_attachments_service_role_only'
    AND (
      qual LIKE '%chat-attachments%'
      OR with_check LIKE '%chat-attachments%'
    )
    -- 'authenticated' = ANY(...) misses the case where roles is the empty
    -- array '{}', which in pg_policies stands for PUBLIC (no TO clause).
    -- A stray PUBLIC-scoped policy applies to every role including
    -- authenticated, so we have to flag those too.
    AND ('authenticated' = ANY(roles) OR cardinality(roles) = 0);

  IF overlap_count > 0 THEN
    RAISE EXCEPTION
      'Stray authenticated-scoped policy on storage.objects references chat-attachments — refusing to migrate. Resolve manually.';
  END IF;
END $$;
