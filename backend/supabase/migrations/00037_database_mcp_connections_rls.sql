-- Migration: tighten access to connection-credential tables + freshdesk RPC
-- Created: 2026-05-15
--
-- Context: `database_connections.connection_uri` stores plaintext Postgres
-- URIs (incl. passwords) and `mcp_connections.auth_config` stores bearer
-- tokens / API keys. Both tables shipped without RLS, and Supabase's
-- default `GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated`
-- meant any signed-up user could read every tenant's secrets via the
-- public PostgREST `/rest/v1/<table>` endpoint.
--
-- The same audit also surfaced `exec_freshdesk_query`: the function is
-- granted EXECUTE to `authenticated`, accepts caller-supplied SQL, and
-- its only safety check (`position('freshdesk_tickets' in ...) > 0`) is
-- bypassable by using `freshdesk_tickets` as an alias on a different
-- table — e.g. `SELECT ... FROM database_connections AS freshdesk_tickets`.
-- The backend always invokes this RPC with service-role, so revoking
-- the `authenticated` grant doesn't change product behaviour.
--
-- Backend posture: all reads/writes to these tables go through service-
-- role (`SUPABASE_SERVICE_KEY` per supabase_client.py:64). service-role
-- bypasses RLS, so the policies below only gate direct PostgREST calls
-- using a non-admin JWT. No frontend code talks to these tables
-- directly — the UI calls backend endpoints which mediate via
-- service-role.
--
-- Out of scope here (deferred to separate PRs per the audit):
--   * Encrypt connection_uri / auth_config at rest (pgcrypto / Vault).
--   * Replace the free-form `exec_freshdesk_query` RPC with a
--     parameterised whitelist of query shapes.

-- =============================================================================
-- 1. exec_freshdesk_query — revoke the dangerous authenticated grant
-- =============================================================================

REVOKE EXECUTE ON FUNCTION public.exec_freshdesk_query(text)
  FROM authenticated, authenticator, PUBLIC;
-- service_role grant from 00033 stays, which is what the backend uses
-- (services/tool_executors/freshdesk_executor.py:263).

-- =============================================================================
-- 2. database_connections RLS
-- =============================================================================

ALTER TABLE database_connections ENABLE ROW LEVEL SECURITY;

-- SELECT: owner, OR connection marked visible_to_all, OR caller has been
-- granted access via the `*_users` join table. Mirrors the access logic
-- already implemented in services/auth/permissions.py.
DROP POLICY IF EXISTS database_connections_select ON database_connections;
CREATE POLICY database_connections_select
ON database_connections FOR SELECT
TO authenticated
USING (
  auth.uid() = owner_user_id
  OR visible_to_all = true
  OR EXISTS (
    SELECT 1 FROM database_connection_users dcu
    WHERE dcu.connection_id = database_connections.id
      AND dcu.user_id = auth.uid()
  )
);

-- Writes (INSERT / UPDATE / DELETE): owner only. The backend gates
-- ownership transfer + invitee changes at the application layer; this
-- policy is the database-level fence behind that.
DROP POLICY IF EXISTS database_connections_insert ON database_connections;
CREATE POLICY database_connections_insert
ON database_connections FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = owner_user_id);

DROP POLICY IF EXISTS database_connections_update ON database_connections;
CREATE POLICY database_connections_update
ON database_connections FOR UPDATE
TO authenticated
USING (auth.uid() = owner_user_id)
WITH CHECK (auth.uid() = owner_user_id);

DROP POLICY IF EXISTS database_connections_delete ON database_connections;
CREATE POLICY database_connections_delete
ON database_connections FOR DELETE
TO authenticated
USING (auth.uid() = owner_user_id);

-- =============================================================================
-- 3. database_connection_users RLS (join table)
-- =============================================================================

ALTER TABLE database_connection_users ENABLE ROW LEVEL SECURITY;

-- SELECT: owner of the parent connection, or the user listed in the row.
-- (Members need to see their own grants so the UI can render
-- "connections shared with me".)
DROP POLICY IF EXISTS database_connection_users_select ON database_connection_users;
CREATE POLICY database_connection_users_select
ON database_connection_users FOR SELECT
TO authenticated
USING (
  user_id = auth.uid()
  OR EXISTS (
    SELECT 1 FROM database_connections dc
    WHERE dc.id = database_connection_users.connection_id
      AND dc.owner_user_id = auth.uid()
  )
);

-- Writes: only the parent connection's owner can grant / revoke members.
DROP POLICY IF EXISTS database_connection_users_insert ON database_connection_users;
CREATE POLICY database_connection_users_insert
ON database_connection_users FOR INSERT
TO authenticated
WITH CHECK (
  EXISTS (
    SELECT 1 FROM database_connections dc
    WHERE dc.id = database_connection_users.connection_id
      AND dc.owner_user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS database_connection_users_delete ON database_connection_users;
CREATE POLICY database_connection_users_delete
ON database_connection_users FOR DELETE
TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM database_connections dc
    WHERE dc.id = database_connection_users.connection_id
      AND dc.owner_user_id = auth.uid()
  )
);

-- =============================================================================
-- 4. mcp_connections RLS — same shape as database_connections
-- =============================================================================

ALTER TABLE mcp_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mcp_connections_select ON mcp_connections;
CREATE POLICY mcp_connections_select
ON mcp_connections FOR SELECT
TO authenticated
USING (
  auth.uid() = owner_user_id
  OR visible_to_all = true
  OR EXISTS (
    SELECT 1 FROM mcp_connection_users mcu
    WHERE mcu.connection_id = mcp_connections.id
      AND mcu.user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS mcp_connections_insert ON mcp_connections;
CREATE POLICY mcp_connections_insert
ON mcp_connections FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = owner_user_id);

DROP POLICY IF EXISTS mcp_connections_update ON mcp_connections;
CREATE POLICY mcp_connections_update
ON mcp_connections FOR UPDATE
TO authenticated
USING (auth.uid() = owner_user_id)
WITH CHECK (auth.uid() = owner_user_id);

DROP POLICY IF EXISTS mcp_connections_delete ON mcp_connections;
CREATE POLICY mcp_connections_delete
ON mcp_connections FOR DELETE
TO authenticated
USING (auth.uid() = owner_user_id);

-- =============================================================================
-- 5. mcp_connection_users RLS (join table)
-- =============================================================================

ALTER TABLE mcp_connection_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mcp_connection_users_select ON mcp_connection_users;
CREATE POLICY mcp_connection_users_select
ON mcp_connection_users FOR SELECT
TO authenticated
USING (
  user_id = auth.uid()
  OR EXISTS (
    SELECT 1 FROM mcp_connections mc
    WHERE mc.id = mcp_connection_users.connection_id
      AND mc.owner_user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS mcp_connection_users_insert ON mcp_connection_users;
CREATE POLICY mcp_connection_users_insert
ON mcp_connection_users FOR INSERT
TO authenticated
WITH CHECK (
  EXISTS (
    SELECT 1 FROM mcp_connections mc
    WHERE mc.id = mcp_connection_users.connection_id
      AND mc.owner_user_id = auth.uid()
  )
);

DROP POLICY IF EXISTS mcp_connection_users_delete ON mcp_connection_users;
CREATE POLICY mcp_connection_users_delete
ON mcp_connection_users FOR DELETE
TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM mcp_connections mc
    WHERE mc.id = mcp_connection_users.connection_id
      AND mc.owner_user_id = auth.uid()
  )
);
