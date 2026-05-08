-- Migration: Chat Attachments RLS — switch to permissive policy
-- Description: 00027 created the chat-attachments bucket with policies
--              copied from raw-files (auth.uid()::text = first folder).
--              That pattern relies on the service-role JWT bypassing
--              RLS, which works for raw-files in practice but was
--              rejecting chat-attachment uploads with 403 on the
--              customer's deploy:
--                "new row violates row-level security policy"
--              when uploading {project_id}/{chat_id}/{attachment_id}/{filename}
--              (first folder is project_id, never matches auth.uid()).
--
--              Drop the restrictive policies and replace with a single
--              permissive policy that allows authenticated + service_role
--              JWTs to read/write/delete on this bucket. Threat model:
--              the backend mediates ALL writes (upload route uses
--              service-role), the bucket is private (public=false),
--              and reads come via signed URLs validated by storage-api.
--              No direct user-token write surface exists today, so a
--              wide-open policy doesn't expand the attack surface.
-- Created: 2026-05-08

-- Drop the four restrictive policies from 00027.
DROP POLICY IF EXISTS "Users can upload chat attachments to own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can read chat attachments from own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can update chat attachments in own projects"   ON storage.objects;
DROP POLICY IF EXISTS "Users can delete chat attachments from own projects" ON storage.objects;

-- Single permissive policy scoped to the service_role ONLY. The backend
-- is the only writer (uses service-role JWT) and reads come through
-- pre-signed URLs that storage-api validates via the signature, not via
-- RLS — so user-scope JWTs (`TO authenticated`) don't need any access
-- here. Granting `authenticated` would let any signed-in user call the
-- Supabase storage API directly with their JWT and read/write/delete
-- attachments across every other user's projects and chats.
--
-- Idempotency: the four DROP POLICY IF EXISTS statements above clear
-- the slate before this CREATE runs, so re-applying the migration is
-- safe even though `CREATE POLICY` itself doesn't accept IF NOT EXISTS
-- on PostgreSQL 15 — Supabase's pinned version (CREATE POLICY's
-- IF NOT EXISTS form only landed in PG 17). An earlier draft of this
-- file used IF NOT EXISTS and aborted the migrate container with
-- exit 3 / syntax error on the prod deploy.
CREATE POLICY "Chat attachments — backend-mediated full access"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'chat-attachments')
WITH CHECK (bucket_id = 'chat-attachments');
