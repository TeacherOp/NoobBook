-- Migration: defense-in-depth revoke of exec_freshdesk_query from anon.
-- Created: 2026-05-16
--
-- Migration 00037 revoked from authenticated, authenticator, and PUBLIC
-- but missed the `anon` role. The function is SECURITY INVOKER so any
-- inner SELECT would still hit the post-PR-2 RLS policies (all
-- TO authenticated) and get denied on database_connections /
-- mcp_connections. That makes anon's access *bounded* but not *zero* —
-- freshdesk_tickets itself doesn't have RLS today, so an attacker
-- pivoting through anon could still exfil tickets if they ever found
-- another way to invoke the RPC. Closing the cleanest possible gate.

REVOKE EXECUTE ON FUNCTION public.exec_freshdesk_query(text) FROM anon;
