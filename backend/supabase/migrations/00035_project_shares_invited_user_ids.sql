-- Migration: project_shares.invited_user_ids
-- Created: 2026-05-14
--
-- Context: invited-mode shares are gated by an array of emails
-- (`invited_emails`) compared against the JWT's `email` claim. With
-- `ENABLE_EMAIL_AUTOCONFIRM=true` (default in our shipped self-host
-- config), the JWT email claim isn't operator-verified — an attacker
-- can sign up with any email string and get a valid session. The
-- string-equality check then lets them through.
--
-- Long-term shape: store invitees as `user_id` UUIDs once we've
-- confirmed mailbox ownership at least once. The viewer_invited()
-- check in share_service.py reads `invited_user_ids` first (fast UUID
-- lookup), then falls back to the email path only when the JWT carries
-- `email_verified=true`. On the email fallback path we lazily promote
-- the matched invitee — remove their email from `invited_emails`, add
-- their `user_id` to `invited_user_ids`. Future requests hit the fast
-- path without trusting the email claim.
--
-- This column ships alongside an autoconfirm flip (env layer) so
-- `email_verified=true` becomes a real signal.

ALTER TABLE project_shares
  ADD COLUMN IF NOT EXISTS invited_user_ids UUID[] NOT NULL DEFAULT '{}';

-- No new index needed: lookups happen via array membership inside
-- `viewer_invited()` after we've already fetched the row by token,
-- which uses the existing `project_shares_non_revoked_token_idx`.

COMMENT ON COLUMN project_shares.invited_user_ids IS
  'Invitees promoted from email→user_id after first verified-email claim. See share_service.viewer_invited().';
