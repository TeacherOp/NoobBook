"""
Mixpanel Integration Service - Query API access for NoobBook chat.

Educational Note: Uses Mixpanel's Service Account auth (HTTP Basic) against
the Query API (https://mixpanel.com/api/query/). No OAuth — admin configures
one service account globally; all users in the app share access to that
Mixpanel project.

Lazy singleton pattern mirroring jira_service.
"""
import json
import logging
import os
import time as _time
from collections import defaultdict
from datetime import date, timedelta
from math import ceil
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class MixpanelService:
    """
    Mixpanel Query API service.

    Config (env vars):
        MIXPANEL_SERVICE_ACCOUNT_USERNAME
        MIXPANEL_SERVICE_ACCOUNT_SECRET
        MIXPANEL_PROJECT_ID
        MIXPANEL_REGION (optional, "us" | "eu" | "in"; default "us")
    """

    REGION_HOSTS = {
        "us": "https://mixpanel.com",
        "eu": "https://eu.mixpanel.com",
        "in": "https://in.mixpanel.com",
    }

    def __init__(self):
        self._auth: Optional[HTTPBasicAuth] = None
        self._project_id: Optional[str] = None
        self._base_url: Optional[str] = None
        self._configured: Optional[bool] = None

    def _load_config(self) -> None:
        if self._configured is not None:
            return

        username = os.getenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", "").strip().strip('"')
        secret = os.getenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", "").strip().strip('"')
        project_id = os.getenv("MIXPANEL_PROJECT_ID", "").strip().strip('"')
        region = os.getenv("MIXPANEL_REGION", "us").strip().lower() or "us"

        host = self.REGION_HOSTS.get(region, self.REGION_HOSTS["us"])
        self._base_url = f"{host}/api/query"
        self._auth = HTTPBasicAuth(username, secret) if username and secret else None
        self._project_id = project_id or None
        self._configured = bool(self._auth and self._project_id)

        if self._configured:
            logger.info("Mixpanel service configured: project_id=%s region=%s", project_id, region)

    def reload_config(self) -> None:
        """Reset cached config so next call re-reads env vars."""
        self._configured = None

    def is_configured(self) -> bool:
        self._load_config()
        return bool(self._configured)

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """
        Call the Mixpanel Query API.

        Educational Note: Mixpanel's Query API returns either JSON objects or
        NDJSON (for /export). The endpoints we use here all return JSON.
        """
        self._load_config()
        if not self._configured:
            return {
                "success": False,
                "error": (
                    "Mixpanel not configured. Please add MIXPANEL_SERVICE_ACCOUNT_USERNAME, "
                    "MIXPANEL_SERVICE_ACCOUNT_SECRET, and MIXPANEL_PROJECT_ID to your .env."
                ),
            }

        # project_id is required on every Query API call
        merged_params = {"project_id": self._project_id}
        if params:
            merged_params.update({k: v for k, v in params.items() if v is not None})

        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {"Accept": "application/json"}

        call_t0 = _time.monotonic()

        def _log(status: int, body_chars: int) -> None:
            """Per-call summary so a 'Mixpanel feels broken' report can be
            traced to the specific endpoint + status. Body content is not
            logged — just its length."""
            ms = int((_time.monotonic() - call_t0) * 1000)
            level = logger.info if status == 200 else logger.warning
            level(
                "MIXPANEL_API endpoint=%s status=%s ms=%d body_chars=%d",
                endpoint, status, ms, body_chars,
            )

        try:
            if method == "GET":
                response = requests.get(
                    url, auth=self._auth, headers=headers, params=merged_params, timeout=30
                )
            elif method == "POST":
                response = requests.post(
                    url, auth=self._auth, headers=headers, data=merged_params, timeout=30
                )
            else:
                return {"success": False, "error": f"Unsupported HTTP method: {method}"}

            _log(response.status_code, len(response.text or ""))

            if response.status_code == 200:
                try:
                    return {"success": True, "data": response.json()}
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid JSON response from Mixpanel: {response.text[:200]}",
                    }
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed. Check service account username/secret.",
                }
            if response.status_code == 402:
                return {
                    "success": False,
                    "error": "Mixpanel rejected the request (payment/quota). See response: "
                    + response.text[:200],
                }
            if response.status_code == 403:
                return {
                    "success": False,
                    "error": "Permission denied. Service account must have access to the project.",
                }
            if response.status_code == 404:
                return {"success": False, "error": f"Not found: {endpoint}"}
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "Rate limit hit (Mixpanel Query API: 60/hr, 5 concurrent). Try again later.",
                }
            return {
                "success": False,
                "error": f"Mixpanel API error: {response.status_code} - {response.text[:200]}",
            }
        except requests.exceptions.Timeout:
            _log(0, 0)
            logger.warning("MIXPANEL_API endpoint=%s error=timeout", endpoint)
            return {"success": False, "error": "Mixpanel request timed out."}
        except requests.exceptions.ConnectionError:
            _log(0, 0)
            logger.warning("MIXPANEL_API endpoint=%s error=connection", endpoint)
            return {"success": False, "error": "Could not connect to Mixpanel API."}
        except Exception as e:
            _log(0, 0)
            logger.warning("MIXPANEL_API endpoint=%s error=%s", endpoint, type(e).__name__)
            return {"success": False, "error": f"Request failed: {str(e)}"}

    # --- Tool methods ---

    def list_events(self, limit: int = 100) -> Dict[str, Any]:
        """
        List event names tracked in the project.

        Endpoint: GET /events/names?type=general&limit=N
        """
        result = self._make_request(
            "events/names",
            params={"type": "general", "limit": min(max(limit, 1), 255)},
        )
        if not result["success"]:
            return result

        names = result["data"]
        if not isinstance(names, list):
            names = []

        return {"success": True, "events": names, "total": len(names)}

    def query_events(
        self,
        event_names: List[str],
        from_date: str,
        to_date: str,
        unit: str = "day",
        event_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Get event counts over time.

        Endpoint: GET /events?event=["A","B"]&from_date=YYYY-MM-DD&to_date=YYYY-MM-DD&unit=day&type=general
        """
        if not event_names:
            return {"success": False, "error": "event_names is required (non-empty list)."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        return self._make_request(
            "events",
            params={
                "event": json.dumps(event_names),
                "from_date": from_date,
                "to_date": to_date,
                "unit": unit,
                "type": event_type,
            },
        )

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: Optional[str] = None,
        where: Optional[str] = None,
        unit: str = "day",
        segmentation_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Segment a single event by a property.

        Endpoint: GET /segmentation?event=X&from_date=Y&to_date=Z&on=properties["..."]&type=general
        """
        if not event:
            return {"success": False, "error": "event is required."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        params: Dict[str, Any] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "unit": unit,
            "type": segmentation_type,
        }
        if on:
            params["on"] = on
        if where:
            params["where"] = where

        return self._make_request("segmentation", params=params)

    def list_funnels(self) -> Dict[str, Any]:
        """List funnels configured in the project. Endpoint: GET /funnels/list"""
        result = self._make_request("funnels/list")
        if not result["success"]:
            return result

        funnels = result["data"]
        if not isinstance(funnels, list):
            funnels = []

        formatted = [
            {"funnel_id": f.get("funnel_id"), "name": f.get("name")}
            for f in funnels
        ]
        return {"success": True, "funnels": formatted, "total": len(formatted)}

    def query_funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        unit: str = "day",
    ) -> Dict[str, Any]:
        """
        Query funnel conversion over time.

        Endpoint: GET /funnels?funnel_id=N&from_date=Y&to_date=Z&unit=day
        """
        if funnel_id is None:
            return {"success": False, "error": "funnel_id is required (integer)."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        return self._make_request(
            "funnels",
            params={
                "funnel_id": funnel_id,
                "from_date": from_date,
                "to_date": to_date,
                "unit": unit,
            },
        )

    def retention(
        self,
        born_event: str,
        event: Optional[str],
        from_date: str,
        to_date: str,
        retention_type: str = "birth",
        unit: str = "day",
    ) -> Dict[str, Any]:
        """
        Retention analysis.

        Endpoint: GET /retention?from_date=Y&to_date=Z&retention_type=birth&born_event=X&event=Y&unit=day
        """
        if not born_event:
            return {"success": False, "error": "born_event is required."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        params: Dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "retention_type": retention_type,
            "born_event": born_event,
            "unit": unit,
        }
        if event:
            params["event"] = event

        return self._make_request("retention", params=params)

    # --- Cohort path analysis (uses /export, separate host) ---

    # Mixpanel /export host is distinct from /api/query/* — see
    # https://developer.mixpanel.com/reference/raw-event-export. Region maps to
    # the `data{,-eu,-in}.mixpanel.com` host family.
    EXPORT_HOSTS = {
        "us": "https://data.mixpanel.com",
        "eu": "https://data-eu.mixpanel.com",
        "in": "https://data-in.mixpanel.com",
    }

    # Defensive memory cap. A 14-day export can yield ~10MB-100MB of NDJSON
    # for typical projects.
    #
    # Memory shape: cohort is O(N) in users; counts is dict[event_name,
    # set[distinct_id]] which is O(N × E) in the worst case (every cohort
    # user fires every event type). For a typical product (cohort size
    # 1k-50k, event types 50-500) that's well under 100MB. The 500k-cohort
    # cap is the safety rail for accidental "no filter" runs — Claude
    # should narrow the date window or trigger_event past this point.
    _EVENTS_AFTER_MAX_COHORT = 500_000

    def _export_request(
        self,
        from_date: str,
        to_date: str,
    ):
        """
        Stream Mixpanel raw events for [from_date, to_date] inclusive.

        Yields parsed event dicts one at a time so callers can process in
        constant memory regardless of payload size.

        Raises a generator-friendly RuntimeError mapped to a clean error
        message at the call site (events_after) when Mixpanel returns
        non-200.
        """
        self._load_config()
        if not self._configured:
            raise RuntimeError(
                "Mixpanel not configured. Please add MIXPANEL_SERVICE_ACCOUNT_USERNAME, "
                "MIXPANEL_SERVICE_ACCOUNT_SECRET, and MIXPANEL_PROJECT_ID to your .env."
            )

        region = (os.getenv("MIXPANEL_REGION", "us").strip().lower() or "us")
        host = self.EXPORT_HOSTS.get(region, self.EXPORT_HOSTS["us"])
        url = f"{host}/api/2.0/export"
        params = {
            "project_id": self._project_id,
            "from_date": from_date,
            "to_date": to_date,
        }

        # stream=True + iter_lines avoids loading the full NDJSON body into
        # memory; for high-volume projects the payload can be 100MB+.
        try:
            with requests.get(
                url, auth=self._auth, params=params, stream=True, timeout=120
            ) as response:
                if response.status_code == 401:
                    raise RuntimeError("Authentication failed. Check service account username/secret.")
                if response.status_code == 402:
                    raise RuntimeError("Mixpanel rejected the request (payment/quota).")
                if response.status_code == 403:
                    raise RuntimeError("Permission denied. Service account must have access to the project.")
                if response.status_code == 429:
                    raise RuntimeError("Mixpanel rate limit hit (60/hr on /export). Try again later.")
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Mixpanel /export error: {response.status_code} - {response.text[:200]}"
                    )

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except ValueError:
                        # Skip malformed lines rather than failing the whole
                        # cohort analysis — Mixpanel occasionally emits a
                        # blank or partial line at the boundary of segments.
                        continue
        except requests.exceptions.Timeout:
            raise RuntimeError("Mixpanel /export request timed out (export may be too large; narrow the date range).")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Could not connect to Mixpanel /export.")

    def events_after(
        self,
        trigger_event: str,
        from_date: str,
        to_date: str,
        window_hours: int = 168,
        top_n: int = 20,
        exclude_trigger: bool = True,
    ) -> Dict[str, Any]:
        """
        Cohort path analysis without JQL.

        Two-pass over Mixpanel /export to keep memory bounded by
        cohort_size + distinct event_names (NOT by total event volume,
        which can be millions for busy projects):

          Pass 1: stream the cohort-window slice; collect every user who
                  fired `trigger_event`, recording each user's *earliest*
                  trigger timestamp.
          Pass 2: stream the post-trigger slice (cohort_end + ceil(
                  window_hours/24) days); for events from cohort users
                  in their per-user forward window, increment a
                  {event_name: set(distinct_id)} counts dict.

        Two API calls (vs. one) is the right trade — Mixpanel's /export
        rate limit is 60/hr and chat is interactive, so the doubling is
        invisible in practice and avoids materialising the full event
        stream in memory.

        Returns the standard {"success": bool, ...} envelope used by the
        rest of this service.
        """
        if not trigger_event:
            return {"success": False, "error": "trigger_event is required."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}
        if window_hours <= 0:
            return {"success": False, "error": "window_hours must be positive."}
        # Guard against `top_n=0` silently producing an empty list — that
        # masks a successful run as "no events found" and confuses the caller.
        if top_n <= 0:
            return {"success": False, "error": "top_n must be positive."}

        try:
            # Validate both ends — fail fast instead of letting Mixpanel
            # surface a vague 400 from /export.
            date.fromisoformat(from_date)
            cohort_end = date.fromisoformat(to_date)
            buffer_days = ceil(window_hours / 24)
            export_end = (cohort_end + timedelta(days=buffer_days)).isoformat()
        except ValueError as exc:
            return {"success": False, "error": f"Invalid date: {exc}"}

        window_seconds = window_hours * 3600

        # ── Pass 1: build the cohort ────────────────────────────────
        # Stream only the cohort window — earlier/later trigger fires
        # don't belong to this cohort. Memory is bounded by cohort_size.
        cohort: Dict[str, int] = {}  # distinct_id -> earliest trigger ts (s)
        try:
            for evt in self._export_request(from_date=from_date, to_date=to_date):
                if evt.get("event") != trigger_event:
                    continue
                props = evt.get("properties") or {}
                uid = props.get("distinct_id") or props.get("$distinct_id")
                ts = props.get("time")
                if not (uid and isinstance(ts, (int, float))):
                    continue
                ts_int = int(ts)
                # Earliest trigger wins so the forward window starts at
                # the user's first qualifying action.
                if uid not in cohort or ts_int < cohort[uid]:
                    cohort[uid] = ts_int
                if len(cohort) >= self._EVENTS_AFTER_MAX_COHORT:
                    return {
                        "success": False,
                        "error": (
                            f"Cohort reached the {self._EVENTS_AFTER_MAX_COHORT:,}-user cap — "
                            "narrow from_date/to_date or use a more specific trigger_event."
                        ),
                    }
        except RuntimeError as exc:
            return {"success": False, "error": str(exc)}

        if not cohort:
            return {
                "success": True,
                "data": {
                    "trigger_event": trigger_event,
                    "from_date": from_date,
                    "to_date": to_date,
                    "window_hours": window_hours,
                    "cohort_size": 0,
                    "top_events": [],
                },
            }

        # ── Pass 2: count post-trigger events per cohort user ──────
        # Stream the full export window (cohort_window + forward buffer)
        # and aggregate inline. Memory is bounded by distinct event_name
        # × distinct cohort users (typically < a few MB).
        counts: Dict[str, set] = defaultdict(set)
        try:
            for evt in self._export_request(from_date=from_date, to_date=export_end):
                ev_name = evt.get("event")
                if not ev_name:
                    continue
                if exclude_trigger and ev_name == trigger_event:
                    continue
                props = evt.get("properties") or {}
                uid = props.get("distinct_id") or props.get("$distinct_id")
                ts = props.get("time")
                if not (uid and isinstance(ts, (int, float))):
                    continue
                trigger_ts = cohort.get(uid)
                if trigger_ts is None:
                    continue
                delta = ts - trigger_ts
                if 0 < delta <= window_seconds:
                    counts[ev_name].add(uid)
        except RuntimeError as exc:
            return {"success": False, "error": str(exc)}

        cohort_size = len(cohort)
        ranked = sorted(counts.items(), key=lambda kv: -len(kv[1]))[:top_n]
        top_events = [
            {
                "event": name,
                "users": len(uids),
                "pct_of_cohort": round(100 * len(uids) / cohort_size, 1),
            }
            for name, uids in ranked
        ]

        return {
            "success": True,
            "data": {
                "trigger_event": trigger_event,
                "from_date": from_date,
                "to_date": to_date,
                "window_hours": window_hours,
                "cohort_size": cohort_size,
                "top_events": top_events,
            },
        }


# Singleton instance
mixpanel_service = MixpanelService()
