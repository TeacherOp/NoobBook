"""
Freshdesk Executor - Runs SQL queries against the global freshdesk_tickets table.

Educational Note: Unlike database_executor which connects to external databases,
this executor queries the local Supabase PostgreSQL directly since Freshdesk
tickets are synced into a global table. All tickets belong to the same Freshdesk
account, so no per-source scoping is needed.
"""

import logging
import os
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

UNSAFE_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# Strip single-quoted strings, double-quoted identifiers, line comments,
# and block comments BEFORE the keyword check. Without this, legitimate
# SQL like `WHERE description ILIKE '%customer wants to update plan%'`
# gets rejected as "Only SELECT queries are allowed" because the word
# `update` inside the string literal trips UNSAFE_SQL_RE. Each pattern
# replaces the matched span with an empty token of the same kind so any
# code that cares about lexical structure (none here today, but defensive)
# stays balanced.
_SQL_STRING_RE         = re.compile(r"'(?:''|[^'])*'", re.DOTALL)
_SQL_QUOTED_IDENT_RE   = re.compile(r'"(?:""|[^"])*"', re.DOTALL)
_SQL_BLOCK_COMMENT_RE  = re.compile(r"/\*.*?\*/", re.DOTALL)
_SQL_LINE_COMMENT_RE   = re.compile(r"--[^\n]*")


def _strip_sql_strings_and_comments(sql: str) -> str:
    """Return `sql` with string literals and comments removed so the
    keyword regex sees only real SQL tokens."""
    sql = _SQL_STRING_RE.sub("''", sql)
    sql = _SQL_QUOTED_IDENT_RE.sub('""', sql)
    sql = _SQL_BLOCK_COMMENT_RE.sub("", sql)
    sql = _SQL_LINE_COMMENT_RE.sub("", sql)
    return sql

FRESHDESK_SCHEMA = """
freshdesk_tickets table columns:
- ticket_id (BIGINT): Freshdesk ticket ID (unique)
- subject (TEXT): Ticket subject
- description_text (TEXT): Ticket body
- status (TEXT): Open, Pending, Resolved, Closed, Waiting on Customer, Waiting on Third Party
- priority (TEXT): Low, Medium, High, Urgent
- ticket_type (TEXT): Ticket category type
- source_channel (TEXT): Email, Portal, Phone, Chat, etc.
- requester_name (TEXT), requester_email (TEXT)
- agent_name (TEXT), agent_email (TEXT)
- group_name (TEXT), product_name (TEXT), company_name (TEXT)
- tags (TEXT[])
- ticket_created_at (TIMESTAMPTZ), ticket_updated_at (TIMESTAMPTZ)
- due_by (TIMESTAMPTZ), resolved_at (TIMESTAMPTZ), closed_at (TIMESTAMPTZ)
- first_responded_at (TIMESTAMPTZ)
- resolution_time_hours (NUMERIC), first_response_time_hours (NUMERIC)
- is_escalated (BOOLEAN), custom_fields (JSONB)

Note: `category` and `subcategory` columns exist on the table but are
not populated by the sync service — treat them as always NULL. Use
`ticket_type` for similar grouping needs.
"""


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert non-JSON-serializable types (datetime, Decimal) to strings."""
    for key, val in row.items():
        if isinstance(val, (datetime, date)):
            row[key] = val.isoformat()
        elif isinstance(val, Decimal):
            row[key] = float(val)
    return row


class FreshdeskExecutor:
    """Executes Freshdesk agent tools against the global freshdesk_tickets table."""

    def __init__(self):
        self._conn = None

    def _get_connection_string(self) -> str:
        """Get PostgreSQL connection string for local Supabase.
        Prefers SUPABASE_DB_URL env var, falls back to constructing from parts."""
        db_url = os.getenv("SUPABASE_DB_URL")
        if db_url:
            return db_url
        host = os.getenv("POSTGRES_HOST", "supabase-db")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        return f"postgresql://postgres:{password}@{host}:{port}/{db}"

    def _get_connection(self):
        """Get or create a psycopg2 connection."""
        if self._conn and not self._conn.closed:
            try:
                self._conn.cursor().execute("SELECT 1")
                return self._conn
            except Exception:
                self._conn = None
        conn_str = self._get_connection_string()
        logger.info("Freshdesk executor connecting to: %s",
                     conn_str.split("@")[-1] if "@" in conn_str else "unknown")
        self._conn = psycopg2.connect(conn_str, connect_timeout=5)
        self._conn.autocommit = True
        return self._conn

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def validate_connection(self) -> bool:
        """
        Check that we can reach the freshdesk_tickets table.

        Goes through the Supabase REST client (same path the sync service
        uses successfully), NOT psycopg2 — the direct DB connection is a
        separate code path that often fails in production deployments
        where only the Supabase API gateway is reachable. As long as the
        REST path works the agent can at least pre-flight; query_runner
        will surface a real error later if psycopg2 itself can't connect.
        """
        try:
            from app.services.integrations.supabase import get_supabase

            supabase = get_supabase()
            (
                supabase.table("freshdesk_tickets")
                .select("ticket_id", count="exact")
                .limit(1)
                .execute()
            )
            return True
        except Exception as e:
            logger.error("Freshdesk executor: REST validate failed: %s", e)
            return False

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any],
        project_id: str, source_id: str,
    ) -> Tuple[Dict[str, Any], bool]:
        """Execute a Freshdesk agent tool. Returns (result, is_termination)."""
        if tool_name == "schema_info":
            return self.get_schema_info(), False
        elif tool_name == "query_runner":
            return self._query_runner(tool_input), False
        elif tool_name == "return_ticket_analysis":
            return tool_input, True
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def get_schema_info(self) -> Dict[str, Any]:
        """Return the freshdesk_tickets schema and global ticket count.

        Uses Supabase REST for the count (same reasoning as
        validate_connection above). Falls back to psycopg2 if REST fails
        — that way deployments without REST access still work.
        """
        # REST path — primary, most reliable.
        try:
            from app.services.integrations.supabase import get_supabase

            supabase = get_supabase()
            resp = (
                supabase.table("freshdesk_tickets")
                .select("ticket_id", count="exact")
                .limit(1)
                .execute()
            )
            count = getattr(resp, "count", None)
            if count is None and isinstance(resp, dict):
                count = resp.get("count")
            return {
                "success": True,
                "schema": FRESHDESK_SCHEMA.strip(),
                "ticket_count": count or 0,
            }
        except Exception as rest_exc:
            logger.warning("Freshdesk schema_info via REST failed (%s); falling back to psycopg2", rest_exc)

        # Fallback: direct psycopg2 connection.
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM freshdesk_tickets")
            row = cur.fetchone()
            count = row[0] if row else 0
            cur.close()
            return {
                "success": True,
                "schema": FRESHDESK_SCHEMA.strip(),
                "ticket_count": count,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _query_runner(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a read-only SQL query against the global freshdesk_tickets table.

        Two paths, tried in order:
          1. Supabase REST RPC (`exec_freshdesk_query`) — works in any
             deployment where the backend can already reach Supabase via
             the API gateway. This is the common case, including Coolify
             and managed-Supabase setups where direct DB access is blocked.
          2. Direct psycopg2 — fallback for the bundled docker-compose
             stack and for older deployments that haven't applied
             migration 00025 yet.
        """
        sql = (tool_input.get("sql_query") or "").strip()
        if not sql:
            return {"success": False, "error": "sql_query is required"}

        # Validate read-only — but only against the SQL's actual tokens.
        # Without stripping string literals first, queries that legitimately
        # contain words like "update" inside a WHERE filter on description
        # text get rejected and burn an agent iteration.
        sql_for_check = _strip_sql_strings_and_comments(sql)
        if UNSAFE_SQL_RE.search(sql_for_check):
            return {"success": False, "error": "Only SELECT queries are allowed"}

        # Must reference freshdesk_tickets — same stripping applied so a
        # mention inside a string literal doesn't satisfy this check
        # (defense in depth; the RPC enforces this server-side too).
        if "freshdesk_tickets" not in sql_for_check.lower():
            return {"success": False, "error": "Query must reference freshdesk_tickets table"}

        rpc_result = self._run_via_rpc(sql)
        if rpc_result is not None:
            return rpc_result
        return self._run_via_psycopg2(sql)

    def _run_via_rpc(self, sql: str) -> Dict[str, Any] | None:
        """
        Try the PostgREST `exec_freshdesk_query` RPC.

        Returns the formatted result on success, or `None` *only* when the
        RPC function itself is unavailable (PGRST202 — function not found —
        or any non-PostgREST error like a transport failure). When the
        function exists but the user's SQL hit a Postgres error, we return
        the error directly so the agent can correct it on the next
        iteration; falling back to psycopg2 there would hide the real cause
        behind a connection-refused message in deployments that don't have
        a direct DB route.
        """
        try:
            # Dedicated service-role client (defense in depth). Migration
            # 00037 revoked EXECUTE on this RPC from `authenticated`,
            # leaving only `service_role`. Even with the auth-verifier
            # fix keeping gotrue events off the data singleton, this
            # callsite must NEVER run as `authenticated` or it 42501-s,
            # so we pin it to a client whose Authorization header is
            # guaranteed-immutable for the life of the process.
            from app.services.integrations.supabase import get_service_role_client
            from postgrest.exceptions import APIError

            supabase = get_service_role_client()
            start = time.time()
            resp = supabase.rpc("exec_freshdesk_query", {"sql_query": sql}).execute()
            elapsed = round((time.time() - start) * 1000, 1)

            rows = resp.data if isinstance(resp.data, list) else []
            # Defensive: PostgREST returns None for an empty jsonb result.
            if rows is None:
                rows = []
            column_names = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
            truncated = len(rows) >= 100

            result = {
                "success": True,
                "query": sql,
                "row_count": len(rows),
                "results": rows,
                "column_names": column_names,
                "execution_time_ms": elapsed,
                "truncated": truncated,
            }
            if truncated:
                result["warning"] = (
                    "Results limited to 100 rows. Use GROUP BY, COUNT, or LIMIT to get aggregated data."
                )
            return result
        except APIError as api_exc:
            code = (api_exc.code or "").upper()
            # PGRST202 = function not found in the schema cache. PGRST200
            # is "matching procedure not found" (signature mismatch). Both
            # mean migration 00025 hasn't been applied — fall back.
            if code in ("PGRST202", "PGRST200", "42883"):  # 42883 = undefined_function
                logger.info(
                    "Freshdesk RPC unavailable (code=%s); falling back to psycopg2", code
                )
                return None
            # Real query error from inside the function (bad SQL, missing
            # column, validation rejection). Surface it so the agent can
            # adjust on its next iteration.
            logger.warning("Freshdesk RPC query error: %s", api_exc)
            return {
                "success": False,
                "error": api_exc.message or str(api_exc),
                "query": sql,
            }
        except Exception as exc:
            # Network / client-init issues (e.g. SUPABASE_URL unreachable).
            # Try psycopg2 — it might be a deployment where direct DB
            # access works even when REST doesn't.
            logger.info(
                "Freshdesk RPC failed at the transport layer (%s); falling back to psycopg2",
                exc,
            )
            return None

    def _run_via_psycopg2(self, sql: str) -> Dict[str, Any]:
        """Direct-Postgres fallback. Requires SUPABASE_DB_URL or POSTGRES_*
        env vars and network access to the Postgres container."""
        try:
            try:
                conn = self._get_connection()
            except Exception as conn_exc:
                # Surface a clearly-attributed connection failure so the
                # model doesn't conflate a misconfigured DB with a
                # genuine empty-result. The chat AI uses the `error`
                # text verbatim when paraphrasing.
                logger.error("Freshdesk query_runner: psycopg2 connect failed: %s", conn_exc)
                return {
                    "success": False,
                    "error": (
                        "Cannot reach the Freshdesk tickets database. "
                        "Apply the latest migrations (00025 adds an RPC fallback that "
                        "needs no extra env vars) or set SUPABASE_DB_URL "
                        "(or POSTGRES_HOST + POSTGRES_PASSWORD) in the backend "
                        f"environment. Underlying error: {conn_exc}"
                    ),
                    "query": sql,
                }
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Set query timeout
            cur.execute("SET statement_timeout = 10000")

            start = time.time()
            cur.execute(sql)
            rows = cur.fetchmany(100)
            elapsed = round((time.time() - start) * 1000, 1)

            results = [_serialize_row(dict(r)) for r in rows]
            column_names = [desc[0] for desc in cur.description] if cur.description else []
            truncated = len(results) == 100

            cur.close()

            result = {
                "success": True,
                "query": sql,
                "row_count": len(results),
                "results": results,
                "column_names": column_names,
                "execution_time_ms": elapsed,
                "truncated": truncated,
            }
            if truncated:
                result["warning"] = "Results limited to 100 rows. Use GROUP BY, COUNT, or LIMIT to get aggregated data."
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "query": sql}


freshdesk_executor = FreshdeskExecutor()
