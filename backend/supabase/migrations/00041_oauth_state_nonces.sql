-- Migration: oauth_state_nonces — single-use nonces for the signed OAuth
-- `state` parameter.
-- Created: 2026-05-16
--
-- The nonce protects against state replay: the worker that mints the
-- auth URL inserts a row; the callback DELETEs by primary key and
-- treats "0 rows affected" as a replay/unknown rejection. Persisting
-- in Supabase (instead of an in-process dict) means the mint and the
-- verify can land on different gunicorn workers without one losing
-- the other's state.
--
-- RLS enabled with no policies means only the service-role JWT can
-- read/write this table — exactly what we want: the backend (which
-- uses service_role) handles the mint and verify; no authenticated or
-- anon caller has any business touching this table directly.

CREATE TABLE IF NOT EXISTS oauth_state_nonces (
  nonce      TEXT PRIMARY KEY,
  user_id    UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Supports the periodic prune query.
CREATE INDEX IF NOT EXISTS oauth_state_nonces_created_idx
  ON oauth_state_nonces (created_at);

ALTER TABLE oauth_state_nonces ENABLE ROW LEVEL SECURITY;
-- Intentionally no policies: RLS-on without policies denies all
-- access except service_role, which bypasses RLS by design.

COMMENT ON TABLE oauth_state_nonces IS
  'Single-use nonces issued for the HMAC-signed Google OAuth `state` parameter. Deleted on first successful verify_state(). Rows older than the 10-minute TTL are pruned opportunistically by sign_state().';
