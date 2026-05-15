-- Migration: promote_share_invitee — atomic email→user_id promotion
-- Created: 2026-05-15
--
-- Context: share_service.viewer_invited() lazily promotes an invitee
-- from invited_emails → invited_user_ids on first verified-email claim.
-- The original implementation read the row, computed new arrays in
-- Python, and wrote them back — a textbook read-modify-write race.
-- Two concurrent invitees both reading the same stale snapshot would
-- each overwrite the other's promotion, and the loser ended up in
-- neither list — permanently locked out of the share.
--
-- This RPC does the whole transition in a single UPDATE statement.
-- Postgres locks the row for the duration of the UPDATE, so two
-- concurrent calls serialize cleanly:
--
--   Tx A: array_remove([A,B], 'a@x') → [B];   array_append([], uid_A) → [uid_A]
--   Tx B (after A commits): array_remove([B], 'b@x') → [];  array_append([uid_A], uid_B) → [uid_A, uid_B]
--
-- Both invitees survive. SECURITY DEFINER is correct here because the
-- caller's authority to mutate this row has already been established by
-- the application-layer check in viewer_invited() (the matched email
-- proved mailbox ownership for *this* share's invitee list). The RPC
-- itself doesn't trust the caller's identity claims — it only mutates
-- the specific (share_id, email, user_id) tuple it was asked to.

CREATE OR REPLACE FUNCTION promote_share_invitee(
  p_share_id UUID,
  p_email TEXT,
  p_user_id UUID
) RETURNS VOID
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE project_shares
  SET
    invited_emails   = array_remove(invited_emails, p_email),
    invited_user_ids = array_append(invited_user_ids, p_user_id)
  WHERE id = p_share_id
    -- Defensive guard: don't append duplicate user_ids if a
    -- concurrent transaction already promoted this user.
    AND NOT (p_user_id = ANY(invited_user_ids));
$$;

-- The backend calls this via the service-role JWT.
GRANT EXECUTE ON FUNCTION promote_share_invitee(UUID, TEXT, UUID) TO service_role;
-- Authenticated callers must NOT call this directly — only the
-- viewer_invited() flow on the backend can, after verifying mailbox
-- ownership via the email_verified JWT claim + email-in-invitees match.
REVOKE EXECUTE ON FUNCTION promote_share_invitee(UUID, TEXT, UUID) FROM PUBLIC, authenticated, anon;

COMMENT ON FUNCTION promote_share_invitee IS
  'Atomic helper for share_service.viewer_invited(). Backend-only (service_role grant). Promotes one invitee from invited_emails to invited_user_ids in a single UPDATE.';
