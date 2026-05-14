"""
Freshdesk Sync Service - Syncs Freshdesk tickets into local Supabase table.

Educational Note: This service bridges the Freshdesk API and local storage.
It fetches tickets from the Freshdesk API, transforms them with resolved
names and computed metrics, and upserts them into the `freshdesk_tickets`
Supabase table for fast local querying by the analysis agent.

Two sync modes:
- backfill: Fetches tickets updated in the last N days (initial import)
- incremental: Fetches tickets updated since the last sync timestamp
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.integrations.freshdesk.freshdesk_service import (
    freshdesk_service,
    STATUS_MAP,
    PRIORITY_MAP,
    SOURCE_MAP,
)
from app.services.integrations.supabase import get_supabase

logger = logging.getLogger(__name__)


class FreshdeskSyncService:
    """
    Service for syncing Freshdesk ticket data into local Supabase tables.

    Educational Note: By storing ticket data locally, the analysis agent
    can run fast SQL queries without hitting the Freshdesk API for every
    question. The sync can be re-run to keep data fresh.
    """

    def sync_tickets(
        self,
        project_id: str,
        source_id: str,
        mode: str = "backfill",
        days_back: int = 90,
    ) -> Dict[str, int]:
        """
        Sync tickets from Freshdesk into the local freshdesk_tickets table.

        Supports cancellation via task_service.is_target_cancelled() and
        reports progress by updating the source's processing_info.
        """
        from app.services.background_services import task_service

        if not freshdesk_service.is_configured():
            return {
                "tickets_fetched": 0, "tickets_upserted": 0,
                "errors": 1,
                "error_message": "Freshdesk not configured",
            }

        # `tickets_upserted` counts every row inserted-or-updated. We can't
        # cheaply distinguish create vs update inside Supabase's batch
        # upsert path, so the previous separate "created" / "updated"
        # counters were misleading (one was always zero).
        stats = {
            "tickets_fetched": 0, "tickets_upserted": 0,
            "errors": 0,
        }

        def _is_cancelled() -> bool:
            return task_service.is_target_cancelled(source_id)

        _sync_start = time.time()

        def _on_progress(total_fetched: int, rate_info: dict = None) -> None:
            """Update source processing_info with live ticket count + ETA."""
            try:
                from app.services.source_services import source_service
                elapsed = time.time() - _sync_start
                info: Dict[str, Any] = {
                    "syncing": True,
                    "tickets_fetched": total_fetched,
                    "mode": mode,
                }
                if rate_info:
                    rate_total = rate_info.get("rate_total", 50)
                    info["rate_limit"] = rate_total
                    # ETA calculation: based on actual throughput so far
                    # tickets_per_second = total_fetched / elapsed
                    # We can't know total tickets ahead of time, so estimate
                    # based on rate limit: at rate_total req/min with 100 tickets/page,
                    # max throughput = rate_total * 100 tickets/min
                    # For now, show pages fetched and rate — the elapsed timer
                    # in the frontend already shows how long it's been running
                    if elapsed > 2 and total_fetched > 0:
                        tickets_per_sec = total_fetched / elapsed
                        info["tickets_per_sec"] = round(tickets_per_sec, 1)
                source_service.update_source(project_id, source_id, processing_info=info)
            except Exception as exc:
                # Non-critical: progress reporting is best-effort. But log
                # so a broken DB connection doesn't silently hide every
                # progress tick.
                logger.warning("Freshdesk progress update failed: %s", exc)

        try:
            freshdesk_service.populate_caches()

            # Use batched fetch for backfill (handles 50k+ tickets via date-range windows)
            # Use single fetch for incremental (typically small number of recent tickets)
            if mode == "backfill":
                raw_tickets = freshdesk_service.fetch_all_tickets_batched(
                    days_back=days_back,
                    batch_days=5,
                    cancel_check=_is_cancelled,
                    on_progress=_on_progress,
                )
            else:
                updated_since = self._get_updated_since(source_id, mode, days_back)
                raw_tickets = freshdesk_service.fetch_all_tickets(
                    updated_since=updated_since,
                    cancel_check=_is_cancelled,
                    on_progress=_on_progress,
                )

            stats["tickets_fetched"] = len(raw_tickets)

            if _is_cancelled():
                stats["cancelled"] = True
                return stats

            if not raw_tickets:
                logger.info(
                    "Freshdesk sync: no tickets found (source_id=%s, mode=%s)",
                    source_id, mode,
                )
                return stats

            # Transform and batch-upsert tickets (100 at a time for performance)
            batch: List[Dict] = []
            for raw_ticket in raw_tickets:
                try:
                    transformed = self._transform_ticket(raw_ticket, source_id, project_id)
                    batch.append(transformed)
                except Exception as e:
                    stats["errors"] += 1
                    logger.error("Transform error for ticket %s: %s", raw_ticket.get("id"), e)

                if len(batch) >= 100:
                    upserted = self._upsert_batch(batch)
                    stats["tickets_upserted"] += upserted
                    stats["errors"] += len(batch) - upserted
                    batch = []

            # Final batch
            if batch:
                upserted = self._upsert_batch(batch)
                stats["tickets_upserted"] += upserted
                stats["errors"] += len(batch) - upserted

            logger.info(
                "Freshdesk sync complete (source_id=%s): fetched=%d, upserted=%d, errors=%d",
                source_id,
                stats["tickets_fetched"],
                stats["tickets_upserted"],
                stats["errors"],
            )

        except Exception as e:
            logger.exception("Freshdesk sync failed (source_id=%s): %s", source_id, e)
            stats["errors"] += 1

        return stats

    def get_sync_stats(self, source_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about synced Freshdesk tickets (global).

        Educational Note: Tickets are stored globally (not per-source), so
        stats reflect the entire Freshdesk account regardless of which
        project triggered the sync.
        """
        try:
            supabase = get_supabase()

            # Total ticket count (global)
            count_result = (
                supabase.table("freshdesk_tickets")
                .select("id", count="exact")
                .execute()
            )
            ticket_count = count_result.count if count_result.count is not None else 0

            if ticket_count == 0:
                return {
                    "ticket_count": 0,
                    "status_breakdown": {},
                    "date_range": {"earliest": None, "latest": None},
                }

            # Status breakdown
            tickets_result = (
                supabase.table("freshdesk_tickets")
                .select("status")
                .execute()
            )
            status_counts: Dict[str, int] = {}
            for row in tickets_result.data or []:
                status = row.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            # Date range
            earliest_result = (
                supabase.table("freshdesk_tickets")
                .select("created_at")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            latest_result = (
                supabase.table("freshdesk_tickets")
                .select("created_at")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            earliest = (
                earliest_result.data[0].get("created_at")
                if earliest_result.data
                else None
            )
            latest = (
                latest_result.data[0].get("created_at")
                if latest_result.data
                else None
            )

            return {
                "ticket_count": ticket_count,
                "status_breakdown": status_counts,
                "date_range": {"earliest": earliest, "latest": latest},
            }

        except Exception as e:
            logger.error("Failed to get global sync stats: %s", e)
            return {
                "ticket_count": 0,
                "status_breakdown": {},
                "date_range": {"earliest": None, "latest": None},
            }

    def _get_updated_since(
        self, source_id: str, mode: str, days_back: int
    ) -> Optional[str]:
        """
        Determine the updated_since filter based on sync mode.

        Educational Note: Since tickets are global, incremental sync queries
        the max synced_at across ALL tickets (not per-source).
        """
        if mode == "incremental":
            try:
                supabase = get_supabase()
                result = (
                    supabase.table("freshdesk_tickets")
                    .select("synced_at")
                    .order("synced_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    last_synced = result.data[0].get("synced_at")
                    if last_synced:
                        logger.info(
                            "Freshdesk incremental sync since: %s", last_synced
                        )
                        return last_synced
            except Exception as e:
                logger.warning(
                    "Failed to get last sync time, falling back to backfill: %s", e
                )

        # Backfill mode or incremental fallback
        since = datetime.now(timezone.utc) - timedelta(days=days_back)
        return since.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _transform_ticket(
        self, raw_ticket: Dict[str, Any], source_id: str, project_id: str = ""
    ) -> Dict[str, Any]:
        """
        Transform a raw Freshdesk API ticket into the local table schema.

        Educational Note: We resolve numeric IDs to human-readable names
        and compute derived metrics (resolution time, first response time)
        so the analysis agent doesn't need to do these lookups at query time.

        Args:
            raw_ticket: Raw ticket dict from Freshdesk API
            source_id: The source UUID to associate with

        Returns:
            Transformed ticket dict matching freshdesk_tickets table schema
        """
        ticket_id = raw_ticket.get("id")
        stats = raw_ticket.get("stats") or {}
        requester = raw_ticket.get("requester") or {}
        company = raw_ticket.get("company") or {}

        # Resolve names from cached lookup tables
        responder_info = freshdesk_service.resolve_agent(
            raw_ticket.get("responder_id")
        )
        group_name = freshdesk_service.resolve_group(raw_ticket.get("group_id"))
        product_name = freshdesk_service.resolve_product(
            raw_ticket.get("product_id")
        )

        # Compute resolution time in hours
        resolution_time_hours = self._compute_hours_between(
            raw_ticket.get("created_at"),
            stats.get("resolved_at"),
        )

        # Compute first response time in hours
        first_response_time_hours = self._compute_hours_between(
            raw_ticket.get("created_at"),
            stats.get("first_responded_at"),
        )

        return {
            "ticket_id": ticket_id,
            "source_id": source_id,
            "project_id": project_id,
            "subject": raw_ticket.get("subject", ""),
            "description_text": raw_ticket.get("description_text", raw_ticket.get("description", "")),
            "status": STATUS_MAP.get(raw_ticket.get("status", 0), "Unknown"),
            "priority": PRIORITY_MAP.get(raw_ticket.get("priority", 0), "Unknown"),
            "source_channel": SOURCE_MAP.get(raw_ticket.get("source", 0), "Unknown"),
            "ticket_type": raw_ticket.get("type") or None,
            "tags": raw_ticket.get("tags") or [],
            "requester_name": requester.get("name", "Unknown"),
            "requester_email": requester.get("email", ""),
            "requester_id": raw_ticket.get("requester_id"),
            "company_name": company.get("name", "") if isinstance(company, dict) else "",
            "company_id": raw_ticket.get("company_id"),
            "agent_name": responder_info.get("name", "Unassigned"),
            "agent_email": responder_info.get("email", ""),
            "responder_id": raw_ticket.get("responder_id"),
            "group_name": group_name,
            "group_id": raw_ticket.get("group_id"),
            "product_name": product_name,
            "product_id": raw_ticket.get("product_id"),
            "ticket_created_at": raw_ticket.get("created_at"),
            "ticket_updated_at": raw_ticket.get("updated_at"),
            "due_by": raw_ticket.get("due_by"),
            "resolved_at": stats.get("resolved_at"),
            "closed_at": stats.get("closed_at"),
            "first_responded_at": stats.get("first_responded_at"),
            "resolution_time_hours": resolution_time_hours,
            "first_response_time_hours": first_response_time_hours,
            "is_escalated": raw_ticket.get("is_escalated", False),
            "custom_fields": raw_ticket.get("custom_fields", {}),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def _upsert_batch(self, tickets: List[Dict[str, Any]]) -> int:
        """Batch upsert tickets, returning the count actually written.

        Three robustness measures over the naive single-shot upsert:

        1. ``returning="minimal"`` — PostgREST otherwise ships the full
           upserted rowset back through Kong. With 100 freshdesk_tickets
           rows (long ``description_text``, JSONB ``custom_fields``) the
           response can exceed Kong's upstream buffer / timeout and come
           back as ``code 502 / "JSON could not be generated"`` — which
           we saw 2483× in prod. We already have the rows; nothing wants
           the echoed body.

        2. Halving retry on any non-JWT failure — recovers transient 502s
           and the rare row that's pathologically large for the chunked
           response. Walks down to per-row inserts before giving up.

        3. PGRST303 recovery — the singleton supabase client caches the
           service-role JWT it was built with. On self-hosted Supabase
           the JWT can carry an ``exp`` claim; once it stales, every
           call from every service fails with PGRST303 until container
           restart. Reset the singleton (re-reads SUPABASE_SERVICE_KEY
           from env) and retry the batch once. If it persists, we log
           CRITICAL — the key itself needs rotation.

        Returns the count of tickets actually upserted (caller compares
        against the batch length to know how many were dropped).
        """
        if not tickets:
            return 0

        # Imported lazily to avoid pulling in the module at import time.
        from app.services.integrations.supabase.supabase_client import SupabaseClient

        # PGRST303 recovery should fire at most once per top-level batch:
        # the first time we see it, we reset the client and retry the
        # whole batch from the top. Persisting after that means the env
        # key itself is stale — no amount of retrying will help.
        jwt_recovery_done = False

        def _try(rows: List[Dict[str, Any]]) -> int:
            nonlocal jwt_recovery_done
            if not rows:
                return 0
            try:
                get_supabase().table("freshdesk_tickets").upsert(
                    rows,
                    on_conflict="ticket_id",
                    returning="minimal",
                ).execute()
                return len(rows)
            except Exception as exc:
                err_str = str(exc)

                # PGRST303 → JWT expired on the cached service-role
                # client. Rebuild and retry the same rows once.
                if "PGRST303" in err_str:
                    if not jwt_recovery_done:
                        jwt_recovery_done = True
                        logger.warning(
                            "Supabase service-role JWT expired (PGRST303); resetting client and retrying batch (%d rows)",
                            len(rows),
                        )
                        SupabaseClient.reset()
                        return _try(rows)
                    # Recovery already attempted and PGRST303 came back.
                    # Don't fall into the halving branch — every smaller
                    # sub-batch will hit the same expired JWT, end up at
                    # len(rows) == 1, and emit N "Upsert dropped" errors
                    # without ever pointing at the real cause. Emit one
                    # actionable CRITICAL and abandon the rest of the
                    # batch so the operator has a clear signal.
                    logger.critical(
                        "Supabase service-role JWT still expired after client reset — "
                        "the SUPABASE_SERVICE_KEY env value itself is stale. "
                        "Rotate the key in the deployment and restart. "
                        "Dropping %d ticket(s) in this batch.",
                        len(rows),
                    )
                    return 0

                # Single row that still failed → drop it, log with
                # ticket_id so the operator can investigate the
                # specific record.
                if len(rows) == 1:
                    logger.error(
                        "Upsert dropped freshdesk ticket %s: %s",
                        rows[0].get("ticket_id"), exc,
                    )
                    return 0

                # Halve and retry. Recovers transient upstream 502s and
                # isolates any individual row that's too large for the
                # response chunker.
                mid = len(rows) // 2
                logger.warning(
                    "Batch upsert failed (%d rows), halving: %s",
                    len(rows), exc,
                )
                return _try(rows[:mid]) + _try(rows[mid:])

        return _try(tickets)

    @staticmethod
    def _compute_hours_between(
        start_iso: Optional[str], end_iso: Optional[str]
    ) -> Optional[float]:
        """
        Compute hours between two ISO datetime strings.

        Args:
            start_iso: Start datetime in ISO format
            end_iso: End datetime in ISO format

        Returns:
            Hours as float, or None if either timestamp is missing
        """
        if not start_iso or not end_iso:
            return None

        try:
            # Parse ISO strings (handle both Z and +00:00 timezone formats)
            start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
            delta = end - start
            return round(delta.total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Auto-sync: single global background thread for incremental sync
    # Educational Note: Since tickets are stored globally, only one
    # auto-sync thread is needed regardless of how many projects use
    # Freshdesk. Any project can trigger it, but it only runs once.
    # ------------------------------------------------------------------

    _auto_sync_thread: Optional[threading.Thread] = None
    _auto_sync_stop_flag: Optional[threading.Event] = None
    _auto_sync_source_id: Optional[str] = None  # Track which source_id to use for progress
    _auto_sync_project_id: Optional[str] = None
    AUTO_SYNC_INTERVAL_SECONDS = 30 * 60  # 30 minutes

    def start_auto_sync(self, project_id: str, source_id: str) -> None:
        """Start the global auto-sync thread (only one runs at a time)."""
        if self._auto_sync_thread and self._auto_sync_thread.is_alive():
            logger.info("Global auto-sync already running")
            return

        self._auto_sync_source_id = source_id
        self._auto_sync_project_id = project_id
        stop_flag = threading.Event()
        self._auto_sync_stop_flag = stop_flag

        def _sync_loop():
            logger.info("Global Freshdesk auto-sync started (every %ds)", self.AUTO_SYNC_INTERVAL_SECONDS)
            while not stop_flag.is_set():
                stop_flag.wait(self.AUTO_SYNC_INTERVAL_SECONDS)
                if stop_flag.is_set():
                    break
                try:
                    logger.info("Auto-sync running global incremental sync")
                    stats = self.sync_tickets(
                        self._auto_sync_project_id,
                        self._auto_sync_source_id,
                        mode="incremental",
                    )
                    logger.info("Auto-sync complete: %s", stats)
                except Exception as e:
                    logger.error("Auto-sync error: %s", e)
            logger.info("Global auto-sync stopped")

        t = threading.Thread(target=_sync_loop, daemon=True, name="freshdesk-global-sync")
        t.start()
        self._auto_sync_thread = t

    def stop_auto_sync(self, project_id: str = "", source_id: str = "") -> None:
        """Stop the global auto-sync thread."""
        if self._auto_sync_stop_flag:
            self._auto_sync_stop_flag.set()
        self._auto_sync_thread = None
        self._auto_sync_stop_flag = None


# Singleton instance
freshdesk_sync_service = FreshdeskSyncService()
