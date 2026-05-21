"""
Freshdesk Integration Service - Freshdesk API client for NoobBook.

Educational Note: This service provides methods to query Freshdesk tickets
using the Freshdesk REST API v2. It follows NoobBook's service pattern with
lazy-loaded client initialization and environment-based configuration.

Freshdesk uses Basic Auth with the API key as username and 'X' as password.
Rate limiting is handled by checking the X-RateLimit-Remaining response header.
"""
import logging
import os
import time
from typing import Dict, Any, Optional, List, Tuple

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


# Freshdesk ticket field mappings
# Educational Note: Freshdesk stores these as integer codes in the API response.
# We resolve them to human-readable labels for the analysis agent.
STATUS_MAP: Dict[int, str] = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
    6: "Waiting on Customer",
    7: "Waiting on Third Party",
}

PRIORITY_MAP: Dict[int, str] = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Urgent",
}

SOURCE_MAP: Dict[int, str] = {
    1: "Email",
    2: "Portal",
    3: "Phone",
    7: "Chat",
    9: "Feedback Widget",
    10: "Outbound Email",
}


class FreshdeskService:
    """
    Freshdesk API integration service.

    Educational Note: Singleton pattern with lazy client initialization.
    Configuration is read from environment variables on first use.
    Freshdesk API uses Basic Auth: (api_key, 'X').
    """

    def __init__(self):
        """Initialize the Freshdesk service with lazy-loaded configuration."""
        self._api_key: Optional[str] = None
        self._domain: Optional[str] = None
        self._base_url: Optional[str] = None
        self._configured: Optional[bool] = None

        # Caches for name resolution (populated by populate_caches)
        self._agents_cache: Dict[int, Dict[str, str]] = {}
        self._groups_cache: Dict[int, str] = {}
        self._products_cache: Dict[int, str] = {}

        # Sticky "this API key can't read X" flags. Some customer-issued
        # Freshdesk keys are scoped to /tickets only and lack /agents,
        # /groups, /products read scopes. Without these flags every sync
        # re-attempted the fetch and logged the same WARNING — typical
        # prod load was a permission_denied warning every ~30 seconds.
        # Reset on reload_config() so an actual key rotation re-probes.
        self._agents_permission_denied: bool = False
        self._groups_permission_denied: bool = False
        self._products_permission_denied: bool = False

    def _load_config(self) -> None:
        """
        Lazy-load Freshdesk configuration from environment variables.

        Educational Note: Freshdesk API base URL is:
        https://{domain}.freshdesk.com/api/v2
        """
        if self._configured is not None:
            return  # Already loaded

        self._api_key = os.getenv("FRESHDESK_API_KEY", "").strip()
        self._domain = os.getenv("FRESHDESK_DOMAIN", "").strip()

        if self._api_key and self._domain:
            # Strip protocol and trailing slashes if user accidentally included them
            domain = self._domain.replace("https://", "").replace("http://", "").rstrip("/")
            # Handle both "company" and "company.freshdesk.com" formats
            if ".freshdesk.com" not in domain:
                domain = f"{domain}.freshdesk.com"
            self._base_url = f"https://{domain}/api/v2"
            self._configured = True
            logger.info("Freshdesk service configured: %s", domain)
        else:
            self._configured = False

    def reload_config(self) -> None:
        """Reset cached config so next call re-reads from environment."""
        self._configured = None
        self._agents_cache.clear()
        self._groups_cache.clear()
        self._products_cache.clear()
        # Reset permission-denied flags so a key rotation re-probes the
        # endpoints. If the new key has /agents read, the flag will stay
        # False and caches will populate normally on the next sync.
        self._agents_permission_denied = False
        self._groups_permission_denied = False
        self._products_permission_denied = False

    def is_configured(self) -> bool:
        """Check if Freshdesk credentials are configured."""
        self._load_config()
        return self._configured

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        _retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make a GET request to the Freshdesk API with automatic rate-limit retry.

        Educational Note: Freshdesk API uses Basic Auth with the API key as
        username and 'X' as password. Rate limits are communicated via the
        X-RateLimit-Remaining header. On 429 responses, we sleep and retry
        automatically (up to 3 times) instead of failing.
        """
        self._load_config()

        if not self._configured:
            return {
                "success": False,
                "error": "Freshdesk not configured. Please add FRESHDESK_API_KEY and FRESHDESK_DOMAIN to .env",
            }

        max_retries = 3

        try:
            url = f"{self._base_url}/{endpoint}"
            auth = HTTPBasicAuth(self._api_key, "X")
            headers = {"Content-Type": "application/json"}

            call_t0 = time.monotonic()
            response = requests.get(
                url, auth=auth, headers=headers, params=params, timeout=30
            )
            # Per-call summary so mid-sync failures are diagnosable from
            # the bundle alone. Sync runs at the batch level above; this is
            # the per-HTTP-call line.
            log_level = logger.info if response.status_code == 200 else logger.warning
            log_level(
                "FRESHDESK_API endpoint=%s status=%s ms=%d",
                endpoint, response.status_code,
                int((time.monotonic() - call_t0) * 1000),
            )

            # Preemptive rate limit pause — sleep before we exhaust the limit
            rate_remaining_raw = response.headers.get("X-RateLimit-Remaining")
            try:
                rate_remaining_int = int(rate_remaining_raw) if rate_remaining_raw else None
            except (ValueError, TypeError):
                rate_remaining_int = None

            if rate_remaining_int is not None and rate_remaining_int <= 5:
                try:
                    retry_after = int(response.headers.get("Retry-After", "30"))
                except (ValueError, TypeError):
                    retry_after = 30
                logger.warning(
                    "Freshdesk rate limit low (%s remaining). Sleeping %ds.",
                    rate_remaining_raw, retry_after,
                )
                time.sleep(retry_after)

            if response.status_code == 200:
                try:
                    rate_total = int(response.headers.get("X-RateLimit-Total", 50))
                except (ValueError, TypeError):
                    rate_total = 50
                return {
                    "success": True, "data": response.json(),
                    "rate_remaining": rate_remaining_int if rate_remaining_int is not None else rate_total,
                    "rate_total": rate_total,
                }
            elif response.status_code == 429:
                # Rate limited — retry after waiting
                if _retry_count < max_retries:
                    try:
                        retry_after = int(response.headers.get("Retry-After", "60"))
                    except (ValueError, TypeError):
                        retry_after = 60
                    logger.warning(
                        "Freshdesk rate limited (429). Sleeping %ds then retrying (%d/%d).",
                        retry_after, _retry_count + 1, max_retries,
                    )
                    time.sleep(retry_after)
                    return self._make_request(endpoint, params, _retry_count=_retry_count + 1)
                return {"success": False, "error": "Rate limited after max retries."}
            elif response.status_code == 401:
                return {"success": False, "error": "Authentication failed. Check your FRESHDESK_API_KEY."}
            elif response.status_code == 403:
                return {"success": False, "error": "Permission denied. Check your Freshdesk permissions."}
            elif response.status_code == 404:
                return {"success": False, "error": f"Not found: {endpoint}"}
            else:
                return {"success": False, "error": f"Freshdesk API error: {response.status_code} - {response.text[:200]}"}

        except requests.exceptions.Timeout:
            # Mirror the JIRA_API / MIXPANEL_API error-path lines so a
            # network failure mid-sync produces an observable signal in
            # the bundle, not silence.
            logger.warning("FRESHDESK_API endpoint=%s error=timeout", endpoint)
            return {"success": False, "error": "Request timed out."}
        except requests.exceptions.ConnectionError:
            logger.warning("FRESHDESK_API endpoint=%s error=connection", endpoint)
            return {"success": False, "error": "Connection failed. Check FRESHDESK_DOMAIN."}
        except Exception as e:
            logger.warning("FRESHDESK_API endpoint=%s error=%s", endpoint, type(e).__name__)
            return {"success": False, "error": f"Request failed: {str(e)}"}

    def list_tickets(
        self,
        updated_since: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        List tickets with pagination.

        Returns ``(tickets, rate_info)`` so callers can surface the live
        rate-limit headers in the sync UI alongside the ticket payload.
        """
        params: Dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),
            "include": "description,requester,stats,company",
            "order_by": "updated_at",
            "order_type": "desc",
        }

        if updated_since:
            params["updated_since"] = updated_since

        result = self._make_request("tickets", params=params)
        if not result["success"]:
            logger.error("Failed to list tickets (page %d): %s", page, result.get("error"))
            return [], {}

        rate_info = {
            "rate_remaining": result.get("rate_remaining", 0),
            "rate_total": result.get("rate_total", 50),
        }
        return result.get("data", []), rate_info

    def fetch_all_tickets(
        self,
        updated_since: Optional[str] = None,
        cancel_check: Optional[Any] = None,
        on_progress: Optional[Any] = None,
    ) -> List[Dict]:
        """
        Fetch all tickets across all pages with progress + cancellation support.
        on_progress receives (total_fetched, rate_info_dict).
        """
        all_tickets: List[Dict] = []
        page = 1
        per_page = 100

        while True:
            if cancel_check and cancel_check():
                logger.info("Freshdesk fetch cancelled after %d tickets", len(all_tickets))
                break

            tickets, rate_info = self.list_tickets(
                updated_since=updated_since,
                page=page,
                per_page=per_page,
            )

            if not tickets:
                break

            all_tickets.extend(tickets)
            logger.info(
                "Freshdesk: page %d (%d tickets, %d total, rate=%s/%s)",
                page, len(tickets), len(all_tickets),
                rate_info.get("rate_remaining"), rate_info.get("rate_total"),
            )

            if on_progress:
                on_progress(len(all_tickets), rate_info)

            if len(tickets) < per_page:
                break

            page += 1

            if page > 300:
                logger.warning("Freshdesk: hit 300-page safety limit")
                break

        return all_tickets

    def fetch_all_tickets_batched(
        self,
        days_back: int = 90,
        batch_days: int = 5,
        cancel_check: Optional[Any] = None,
        on_progress: Optional[Any] = None,
    ) -> List[Dict]:
        """
        Smart fetch: try a single fetch first, only use date-range batching
        if we hit the 300-page limit (30k+ tickets).

        Educational Note: Freshdesk's updated_since is a >= filter with no
        upper bound, so naively splitting into date-range batches causes
        massive duplication (each batch overlaps with all later batches).
        Instead, we only split when a single fetch proves insufficient.
        """
        from datetime import datetime, timedelta, timezone

        # First, try a single fetch for the full date range
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        all_tickets = self.fetch_all_tickets(
            updated_since=since,
            cancel_check=cancel_check,
            on_progress=on_progress,
        )

        # If we didn't hit the 300-page limit, we got everything
        if len(all_tickets) < 30000:
            return all_tickets

        # Enterprise path: hit the limit, need date-range batching
        # Deduplicate by ticket ID since batches overlap
        logger.warning(
            "Freshdesk: hit 30k limit with single fetch, switching to date-range batching"
        )
        seen_ids = {t.get("id") for t in all_tickets}
        now = datetime.now(timezone.utc)
        num_batches = (days_back + batch_days - 1) // batch_days

        for i in range(num_batches):
            if cancel_check and cancel_check():
                break

            batch_start = now - timedelta(days=min((i + 1) * batch_days, days_back))
            logger.info(
                "Freshdesk batch %d/%d: fetching from %s",
                i + 1, num_batches, batch_start.strftime("%Y-%m-%d"),
            )

            batch_tickets = self.fetch_all_tickets(
                updated_since=batch_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                cancel_check=cancel_check,
                on_progress=lambda total, rate: on_progress(
                    len(all_tickets) + total, rate
                ) if on_progress else None,
            )

            # Deduplicate: only add tickets we haven't seen
            for ticket in batch_tickets:
                tid = ticket.get("id")
                if tid not in seen_ids:
                    seen_ids.add(tid)
                    all_tickets.append(ticket)

            logger.info(
                "Freshdesk batch %d/%d: %d new tickets (total unique: %d)",
                i + 1, num_batches, len(batch_tickets), len(all_tickets),
            )

        return all_tickets

    def populate_caches(self) -> None:
        """
        Populate internal caches for agents, groups, and products.

        Educational Note: Freshdesk tickets reference agents, groups, and products
        by numeric ID. We fetch these lookup tables once and cache them so we can
        resolve IDs to human-readable names during ticket transformation.

        Permission-aware: if a previous sync already discovered the key
        lacks read access for one of these endpoints, we skip the fetch
        without re-attempting (and without re-logging). Resolvers below
        fall back to "Unknown" / numeric ID when a cache is empty, which
        is the existing behavior for empty-result responses anyway.
        """
        # Fetch agents (paginated, typically < 500)
        self._agents_cache.clear()
        if not self._agents_permission_denied:
            page = 1
            while True:
                result = self._make_request("agents", params={"page": page, "per_page": 100})
                if not result["success"]:
                    if self._is_permission_denied(result):
                        # First time we discover this: log once at INFO so
                        # operators can see "agents read isn't granted"
                        # without it becoming a per-sync WARNING. Future
                        # syncs skip the fetch entirely via the flag.
                        self._agents_permission_denied = True
                        logger.info(
                            "Freshdesk key lacks /agents read scope — "
                            "tickets will resolve to numeric agent IDs. "
                            "Grant 'View Agents' to populate agent names."
                        )
                    else:
                        # A non-permission failure (rate limit, network, 5xx)
                        # is worth a WARNING — operators may want to retry.
                        logger.warning(
                            "Failed to fetch agents page %d: %s",
                            page, result.get("error"),
                        )
                    break
                agents = result.get("data", [])
                if not agents:
                    break
                for agent in agents:
                    agent_id = agent.get("id")
                    contact = agent.get("contact", {}) or {}
                    self._agents_cache[agent_id] = {
                        "name": contact.get("name", "Unknown Agent"),
                        "email": contact.get("email", ""),
                    }
                if len(agents) < 100:
                    break
                page += 1

        # Fetch groups
        self._groups_cache.clear()
        if not self._groups_permission_denied:
            result = self._make_request("groups")
            if result["success"]:
                for group in result.get("data", []):
                    self._groups_cache[group.get("id")] = group.get("name", "Unknown Group")
            elif self._is_permission_denied(result):
                self._groups_permission_denied = True
                logger.info(
                    "Freshdesk key lacks /groups read scope — "
                    "tickets will resolve to numeric group IDs."
                )
            else:
                logger.warning("Failed to fetch groups: %s", result.get("error"))

        # Fetch products
        self._products_cache.clear()
        if not self._products_permission_denied:
            result = self._make_request("products")
            if result["success"]:
                for product in result.get("data", []):
                    self._products_cache[product.get("id")] = product.get("name", "Unknown Product")
            elif self._is_permission_denied(result):
                self._products_permission_denied = True
                logger.info(
                    "Freshdesk key lacks /products read scope — "
                    "tickets will resolve to numeric product IDs."
                )
            else:
                logger.warning("Failed to fetch products: %s", result.get("error"))

    @staticmethod
    def _is_permission_denied(result: Dict[str, Any]) -> bool:
        """Detect the specific 403 case from _make_request's error string.
        Kept as a string check (rather than threading the status code
        through the result dict) so this fix doesn't touch the public
        shape of _make_request and risk breaking other callers."""
        return "Permission denied" in (result.get("error") or "")

        logger.info(
            "Freshdesk caches populated: %d agents, %d groups, %d products",
            len(self._agents_cache),
            len(self._groups_cache),
            len(self._products_cache),
        )

    def resolve_agent(self, agent_id: Optional[int]) -> Dict[str, str]:
        """
        Resolve an agent ID to name and email.

        Args:
            agent_id: Freshdesk agent ID

        Returns:
            Dict with 'name' and 'email' keys
        """
        if not agent_id:
            return {"name": "Unassigned", "email": ""}
        cached = self._agents_cache.get(agent_id)
        if cached:
            return cached
        return {"name": f"Agent #{agent_id}", "email": ""}

    def resolve_group(self, group_id: Optional[int]) -> str:
        """
        Resolve a group ID to its name.

        Args:
            group_id: Freshdesk group ID

        Returns:
            Group name string
        """
        if not group_id:
            return "None"
        return self._groups_cache.get(group_id, f"Group #{group_id}")

    def resolve_product(self, product_id: Optional[int]) -> str:
        """
        Resolve a product ID to its name.

        Args:
            product_id: Freshdesk product ID

        Returns:
            Product name string
        """
        if not product_id:
            return "None"
        return self._products_cache.get(product_id, f"Product #{product_id}")


# Singleton instance
freshdesk_service = FreshdeskService()
