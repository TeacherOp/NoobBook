"""
Logs API routes.

Powers the admin "Logs" UI (chat-header button + Settings tab) and accepts
client-side error reports from the frontend so they end up in the same
log stream as backend errors.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from flask import Response, current_app, g, jsonify, request

from app.api.logs import logs_bp
from app.api.logs.bundle import build_bundle
from app.api.logs.redaction import redact_line
from app.services.auth.rbac import require_admin, require_auth
from app.services.data_services.user_service import get_user_service
from app.services.integrations.supabase import get_supabase, is_supabase_enabled
from app.services.log_service import clear_logs as clear_logs_service
from app.utils import logger as logger_module

logger = logging.getLogger(__name__)

# Timestamp shapes accepted (in priority order):
#   - new (dated): `2026-05-20T10:23:44 [ERROR] app.foo [req:abc]: message`
#   - legacy:     `10:23:44 [ERROR] app.foo [req:abc]: message`
#   - oldest:     `10:23:44 [ERROR] app.foo: message`  (pre-req_id archives)
# The dated form was introduced when multi-day support bundles became
# unreadable without dates and the live tail's 12-h midnight heuristic
# became fragile. The legacy shapes are kept so already-rotated archives
# from before the change still display in the admin UI.
# The `[req:...]` group is optional for the oldest archives.
# Loose enough to skip continuation lines (stack-trace inner lines) which we
# still want to include verbatim.
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})\s+"
    r"\[(?P<level>[A-Z]+)\]\s+"
    r"(?P<logger>[\w.\-]+)"
    r"(?:\s+\[req:(?P<req_id>[^\]]*)\])?"
    r":\s*"
    r"(?P<message>.*)$"
)


def _is_dated_ts(ts: str) -> bool:
    """True iff ``ts`` carries the new ``YYYY-MM-DDTHH:MM:SS`` prefix."""
    return len(ts) >= 10 and ts[4] == "-" and ts[7] == "-"


_TAIL_BLOCK_BYTES = 64 * 1024

# Wrap tolerance for the `since` comparison. The log format stores
# "HH:MM:SS" with no date, so a naive lexical compare loses across
# midnight: ``"00:00:01" <= "23:59:55"`` is True, which would make the
# live tail miss every post-midnight entry until the user hit Refresh.
# We treat a backwards gap of more than this many seconds as "the
# entry wrapped past midnight and is actually newer than `since`".
# 12 h is the usual heuristic: a single deployment writing log lines
# more than half a day apart is so rare in practice that it's
# acceptable to defer to the manual Refresh path in that case.
_WRAP_TOLERANCE_SECONDS = 12 * 3600


def _ts_to_seconds(ts: str) -> Optional[int]:
    """Parse an ``HH:MM:SS`` (or trailing portion of ISO-8601) string to
    seconds-since-midnight. Returns ``None`` on malformed input so the
    caller can fall back to a safe inclusion default (i.e. don't drop
    the entry just because we couldn't parse its timestamp)."""
    # Tolerate a leading "YYYY-MM-DDT" prefix so the legacy seconds-based
    # compare still works when we have to mix a dated entry with a legacy
    # cursor (live tail across a deploy boundary).
    if _is_dated_ts(ts):
        ts = ts[11:]
    try:
        h_s, m_s, s_s = ts.split(":", 2)
        # The seconds field can carry a trailing fractional component
        # in some formatters — strip anything after the first 2 chars.
        return int(h_s) * 3600 + int(m_s) * 60 + int(s_s[:2])
    except (ValueError, IndexError):
        return None


def _ts_strictly_after(ts: str, since: str) -> bool:
    """Return True iff ``ts`` is newer than ``since``.

    Three regimes:
      1. Both timestamps dated (ISO-8601) → plain lexical compare works
         because ISO-8601 sorts correctly. No midnight heuristic needed.
      2. Both timestamps legacy ``HH:MM:SS`` → fall through to the
         pre-existing seconds-of-day compare with the 12 h wrap tolerance.
      3. Mixed (one dated + one legacy) → can happen briefly across a
         deploy boundary when the live tail's `since` cursor predates
         the format change. Strip both to the time-of-day portion and
         use the legacy wrap-tolerant compare so we don't black-hole the
         poll window."""
    ts_dated = _is_dated_ts(ts)
    since_dated = _is_dated_ts(since)
    if ts_dated and since_dated:
        return ts > since
    if ts > since:
        return True
    ts_secs = _ts_to_seconds(ts)
    since_secs = _ts_to_seconds(since)
    if ts_secs is None or since_secs is None:
        # Treat malformed input as "potentially newer" so we err on
        # the side of showing the user the entry. Manual Refresh
        # remains the safety net.
        return False
    backwards_gap = since_secs - ts_secs
    return backwards_gap > _WRAP_TOLERANCE_SECONDS


def _read_recent_lines(
    limit: int,
    levels: set[str],
    since: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Tail the active log file and return matching structured lines.

    Reads the whole file once — kept as the safety fallback in case the
    backward-block tail reader raises on a malformed file. The main path
    is `_tail_lines` below, which is O(requested) instead of O(file size)
    and dominates the open-modal latency.

    The optional ``since`` is an "HH:MM:SS" or longer timestamp prefix;
    matching is lexical (the file's timestamps are already "HH:MM:SS").
    """
    if not logger_module.LOG_FILE or not logger_module.LOG_FILE.exists():
        return []

    matched: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    def _flush(entry: dict[str, Any] | None) -> None:
        if not entry or entry["level"] not in levels:
            return
        if since is not None and not _ts_strictly_after(entry["ts"], since):
            return
        matched.append(entry)

    try:
        with logger_module.LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                m = _LINE_RE.match(line)
                if m:
                    _flush(pending)
                    if len(matched) > limit * 4:
                        # Trim early to keep memory bounded on large files.
                        matched = matched[-limit:]
                    pending = {
                        "ts": m.group("ts"),
                        "level": m.group("level"),
                        "logger": m.group("logger"),
                        "req_id": m.group("req_id") or "",
                        "message": redact_line(m.group("message")),
                    }
                else:
                    # Continuation of the previous structured line (stack trace etc.)
                    if pending is not None:
                        pending["message"] += "\n" + redact_line(line)
            _flush(pending)
    except Exception as exc:
        logger.exception("Failed to read log file: %s", exc)
        return []

    return matched[-limit:]


def _find_first_anchor_offset(block: bytes) -> Optional[int]:
    """Return the byte offset of the first complete anchor line in
    ``block``, or ``None`` if no anchor is found.

    "Anchor line" = a line whose start matches ``_LINE_RE`` (i.e. the
    structured ``HH:MM:SS [LEVEL] logger [req:...]: message`` prefix).

    We always skip the *first* line in the block because — when the
    caller is reading mid-file (``pos > 0``) — that line may be a
    partial whose head bytes live in the previous (earlier) block.
    After that we walk newline-by-newline and return the offset of
    the first complete anchor."""
    first_nl = block.find(b"\n")
    if first_nl < 0:
        return None
    cursor = first_nl + 1
    block_len = len(block)
    while cursor < block_len:
        next_nl = block.find(b"\n", cursor)
        line_end = block_len if next_nl < 0 else next_nl
        # Decode just this candidate line — cheaper than decoding the
        # whole block when the first anchor is near the top.
        try:
            line = block[cursor:line_end].decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover — defensive
            line = ""
        if _LINE_RE.match(line):
            return cursor
        if next_nl < 0:
            break
        cursor = next_nl + 1
    return None


def _tail_lines(
    path: Path,
    limit: int,
    levels: set[str],
    since: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Tail-read the log file in 64 KB blocks from the end.

    Stops as soon as we've collected ``limit`` matching anchor lines.
    Anchor lines are those that start with the structured "HH:MM:SS [LEVEL] ..."
    prefix — continuation lines (stack-trace bodies) are folded into the
    previous anchor's ``message`` when we stitch the buffer forward.

    Why a backward tail reader: the previous full-file path was
    O(file size) per request. On Delta's prod box that's measurable
    (200ms+ on slow Docker mounts under load) and the modal pays it on
    every open. This version is O(requested) — typically 1–3 blocks.

    The function is best-effort: on any unexpected error the caller
    falls back to ``_read_recent_lines`` which preserves the original
    whole-file behaviour.

    ``since`` is matched lexically against the "HH:MM:SS" timestamp.
    When set, the loop also stops the moment a candidate anchor's
    timestamp is <= ``since`` AND we've already crossed into earlier
    records — this is the "live tail" fast-path used by the 30 s poll.
    """
    file_size = path.stat().st_size
    if file_size == 0 or limit <= 0:
        return []

    matched: list[dict[str, Any]] = []
    # ``carry`` holds the leading partial line of the more-recently-read
    # (later) block: the next (earlier) block ends mid-line, and that
    # partial belongs to the line whose head lives in the earlier block.
    # So on each iteration we read [earlier_pos, current_pos) and append
    # ``carry`` to recover the full line at the boundary.
    carry = b""

    with path.open("rb") as f:
        pos = file_size
        while pos > 0 and len(matched) < limit:
            read_size = min(_TAIL_BLOCK_BYTES, pos)
            pos -= read_size
            f.seek(pos)
            block = f.read(read_size) + carry
            carry = b""

            if pos > 0:
                # We didn't reach the file head — the first bytes in
                # ``block`` may be (a) a partial line whose head lives
                # in the previous (earlier) block, AND/OR (b) one or
                # more continuation lines (stack-trace bodies) whose
                # anchor lives in the earlier block. Stash both as
                # ``carry`` so the next iteration appends them to the
                # right anchor — splitting only at the first newline
                # would silently drop the continuation lines because
                # ``_parse_block_anchors`` discards continuations with
                # no preceding anchor in the same chunk.
                anchor_offset = _find_first_anchor_offset(block)
                if anchor_offset is None:
                    # No complete anchor line anywhere in this block.
                    # Everything is orphan continuation/partial bytes;
                    # push to carry and keep reading earlier blocks.
                    carry = block
                    continue
                carry = block[:anchor_offset]
                block = block[anchor_offset:]
            # At pos == 0 we have the entire head of the file in
            # ``block`` — no partial-line stripping needed.

            chunk_text = block.decode("utf-8", errors="replace")
            anchors = _parse_block_anchors(chunk_text)
            # Anchors come back in file (chronological) order; walk in
            # reverse so we accumulate newest first and can stop early
            # once we hit ``limit`` matches.
            for entry in reversed(anchors):
                if since is not None and not _ts_strictly_after(entry["ts"], since):
                    # Crossed into already-seen territory — done.
                    return list(reversed(matched))
                if entry["level"] in levels:
                    matched.append(entry)
                    if len(matched) >= limit:
                        break

    return list(reversed(matched))


def _parse_block_anchors(text: str) -> list[dict[str, Any]]:
    """Parse a UTF-8 chunk into a list of anchor entries with stitched
    continuation lines. Returned in chronological (file) order."""
    entries: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for raw in text.splitlines():
        m = _LINE_RE.match(raw)
        if m:
            if pending is not None:
                entries.append(pending)
            pending = {
                "ts": m.group("ts"),
                "level": m.group("level"),
                "logger": m.group("logger"),
                "req_id": m.group("req_id") or "",
                "message": redact_line(m.group("message")),
            }
        else:
            if pending is not None:
                pending["message"] += "\n" + redact_line(raw)
    if pending is not None:
        entries.append(pending)
    return entries


def _get_recent_lines(
    limit: int,
    levels: set[str],
    since: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Public entry point: try the fast tail reader first, fall back to
    the whole-file scan on any unexpected error. The fallback preserves
    the legacy behaviour so a malformed file or transient I/O glitch
    can't black-hole the logs viewer."""
    log_file = logger_module.LOG_FILE
    if not log_file or not log_file.exists():
        return []
    try:
        return _tail_lines(log_file, limit, levels, since=since)
    except Exception as exc:
        logger.warning(
            "Tail reader failed (%s) — falling back to whole-file scan", exc
        )
        return _read_recent_lines(limit, levels, since=since)


@logs_bp.route("/logs/recent", methods=["GET"])
@require_auth
def get_recent_logs():
    """Return last N error/warning lines as JSON.

    Query params:
      - ``n``     : max anchor lines to return (1..1000, default 100).
      - ``level`` : ``errors`` (default) | ``warnings`` | ``all``.
      - ``since`` : optional "HH:MM:SS" or longer prefix. Returns only
                    lines whose timestamp is strictly greater than this.
                    Drives the 30 s incremental "live tail" poll from the
                    LogsModal — the client passes the newest timestamp it
                    already has, and we read just enough from the tail
                    to satisfy the request.

    The hard 1000-line cap still applies even with ``since``, so a stale
    ``since`` can't dump the whole file in one shot.
    """
    try:
        limit = int(request.args.get("n", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 1000))

    level_param = (request.args.get("level") or "errors").lower()
    if level_param == "all":
        levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    elif level_param == "warnings":
        levels = {"WARNING", "ERROR", "CRITICAL"}
    else:
        levels = {"ERROR", "CRITICAL"}

    since_raw = (request.args.get("since") or "").strip() or None
    # Defensive: accept either the new ISO-8601 ``YYYY-MM-DDTHH:MM:SS``
    # form or the legacy ``HH:MM:SS`` form. Anything else is dropped so a
    # client bug can't silently defeat the comparison.
    if since_raw and not re.match(
        r"^(?:\d{4}-\d{2}-\d{2}T)?\d{2}:\d{2}:\d{2}", since_raw
    ):
        since_raw = None

    lines = _get_recent_lines(limit, levels, since=since_raw)
    return jsonify(
        {
            "success": True,
            "lines": lines,
            "log_file_present": bool(logger_module.LOG_FILE and logger_module.LOG_FILE.exists()),
        }
    ), 200


@logs_bp.route("/logs/bundle", methods=["GET"])
@require_auth
def download_bundle():
    """Return the support bundle as a ZIP attachment."""
    try:
        data, filename = build_bundle()
    except Exception as exc:
        logger.exception("Failed to build support bundle")
        return jsonify({"success": False, "error": str(exc)}), 500

    return Response(
        data,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@logs_bp.route("/logs/clear", methods=["POST"])
@require_admin
def clear_logs():
    """Truncate the active log file and remove rotated archives.

    Admin-only: read (`/logs/bundle`) and destroy are asymmetric — any
    authenticated user can pull a copy of the logs, but only admins can
    permanently wipe the server-side diagnostic history (which may be
    the only evidence of a crash or security incident affecting other
    users). The audit log records which admin triggered the clear.

    Surfaced to non-admins in the UI via the "Delete logs from server
    after download" checkbox — that path is gated by this same endpoint,
    so the checkbox is a no-op for non-admins (frontend hides it; if
    they bypass the UI, this returns 403).
    """
    initiator = getattr(g, "user_id", None) or "admin"
    result = clear_logs_service(initiator=str(initiator))
    if not result.get("success"):
        return jsonify(result), 500
    return jsonify(result), 200


# ---------------------------------------------------------------------------
# Per-user "auto-delete on download" preference
# ---------------------------------------------------------------------------

_AUTO_DELETE_SETTINGS_KEY = "auto_delete_logs_on_download"


@logs_bp.route("/logs/preferences", methods=["GET"])
@require_auth
def get_log_preferences():
    """Return the current user's log-related preferences.

    Right now only `auto_delete_on_download` — drives the pre-check of the
    "Delete logs from server after download" checkbox in the bundle dialog.
    """
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return jsonify({"success": False, "error": "missing user"}), 401
    if not is_supabase_enabled():
        return jsonify({"success": True, "auto_delete_on_download": False}), 200
    settings = get_user_service().get_user_settings_raw(user_id)
    return jsonify(
        {
            "success": True,
            "auto_delete_on_download": bool(settings.get(_AUTO_DELETE_SETTINGS_KEY, False)),
        }
    ), 200


@logs_bp.route("/logs/preferences", methods=["PUT"])
@require_auth
def update_log_preferences():
    """Persist the user's log-download preferences in users.settings."""
    user_id = getattr(g, "user_id", None)
    if not user_id:
        return jsonify({"success": False, "error": "missing user"}), 401
    payload = request.get_json(silent=True) or {}
    if "auto_delete_on_download" not in payload:
        return jsonify(
            {"success": False, "error": "auto_delete_on_download is required"}
        ), 400
    value = bool(payload.get("auto_delete_on_download"))
    if not is_supabase_enabled():
        # Best-effort no-op in self-hosted setups without Supabase auth.
        return jsonify({"success": True, "auto_delete_on_download": value}), 200
    saved = get_user_service().set_settings_key(
        user_id, _AUTO_DELETE_SETTINGS_KEY, value
    )
    if not saved:
        return jsonify({"success": False, "error": "could not persist preference"}), 500
    return jsonify({"success": True, "auto_delete_on_download": value}), 200


# ---------------------------------------------------------------------------
# Global "auto-clear logs weekly" admin toggle
# ---------------------------------------------------------------------------

_HOUSEKEEPING_DEFAULT = {"weekly_clear_enabled": True, "last_run_at": None}


def _read_housekeeping() -> dict[str, Any]:
    if not is_supabase_enabled():
        return dict(_HOUSEKEEPING_DEFAULT)
    try:
        client = get_supabase()
        resp = (
            client.table("app_settings")
            .select("log_housekeeping")
            .eq("id", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning("Could not read app_settings.log_housekeeping: %s", exc)
        return dict(_HOUSEKEEPING_DEFAULT)
    rows = resp.data or []
    if not rows:
        return dict(_HOUSEKEEPING_DEFAULT)
    return {**_HOUSEKEEPING_DEFAULT, **(rows[0].get("log_housekeeping") or {})}


@logs_bp.route("/logs/housekeeping", methods=["GET"])
@require_auth
def get_log_housekeeping():
    """Return the global weekly-clear configuration.

    Read is open to any authenticated user so non-admin users can still
    see *when* the next auto-clear is due before they download a bundle.
    """
    config = _read_housekeeping()
    return jsonify(
        {
            "success": True,
            "weekly_clear_enabled": bool(config.get("weekly_clear_enabled", True)),
            "last_run_at": config.get("last_run_at"),
        }
    ), 200


@logs_bp.route("/logs/housekeeping", methods=["PUT"])
@require_admin
def update_log_housekeeping():
    """Admin-only toggle of the weekly auto-clear scheduler."""
    if not is_supabase_enabled():
        return jsonify({"success": False, "error": "supabase not configured"}), 503
    payload = request.get_json(silent=True) or {}
    if "weekly_clear_enabled" not in payload:
        return jsonify(
            {"success": False, "error": "weekly_clear_enabled is required"}
        ), 400
    enabled = bool(payload.get("weekly_clear_enabled"))

    # Re-read inside the write path and conditionally update on the
    # observed last_run_at. Without this gate, a scheduler tick that lands
    # between our read and our write would have its freshly-written
    # last_run_at silently reset to the snapshot value — making the next
    # tick think it's "never run" and clear logs a second time inside the
    # same 7-day window. Mirrors the conditional-UPDATE pattern in
    # log_housekeeping_scheduler._try_update_last_run.
    try:
        client = get_supabase()
        config = _read_housekeeping()
        prev_last_run = config.get("last_run_at")
        new_value = {**config, "weekly_clear_enabled": enabled}
        update_q = (
            client.table("app_settings")
            .update({"log_housekeeping": new_value})
            .eq("id", True)
        )
        if prev_last_run is None:
            update_q = update_q.is_("log_housekeeping->>last_run_at", "null")
        else:
            update_q = update_q.eq("log_housekeeping->>last_run_at", prev_last_run)
        resp = update_q.execute()
    except Exception as exc:
        logger.exception("Failed to update app_settings.log_housekeeping")
        return jsonify({"success": False, "error": str(exc)}), 500
    if not resp.data:
        # Scheduler tick won the race. Re-read so the caller sees the
        # current state and can retry the toggle if it still doesn't match.
        latest = _read_housekeeping()
        return jsonify(
            {
                "success": False,
                "error": (
                    "Configuration changed concurrently — please reload "
                    "and try again."
                ),
                "weekly_clear_enabled": bool(latest.get("weekly_clear_enabled", True)),
                "last_run_at": latest.get("last_run_at"),
            }
        ), 409
    initiator = getattr(g, "user_id", None) or "admin"
    logger.info(
        "Weekly log auto-clear toggled %s by %s",
        "ENABLED" if enabled else "DISABLED",
        initiator,
    )
    return jsonify(
        {
            "success": True,
            "weekly_clear_enabled": enabled,
            "last_run_at": new_value.get("last_run_at"),
        }
    ), 200


@logs_bp.route("/logs/client", methods=["POST"])
@require_auth
def report_client_error():
    """Frontend hook for browser-side errors.

    Authenticated but not admin-gated — any signed-in user reports their
    own browser errors. The error gets written to backend.log via the
    standard logger so it interleaves with server-side events in the
    bundle.

    Note: `api_bp.before_request` already validates the JWT for every
    `/api/v1/*` route that isn't on the auth/health/share allowlist, so
    `@require_auth` here is defense-in-depth — it pins the contract at
    the route level so a future change to `before_request` (e.g. adding
    `/logs/` to the allowlist by accident) can't silently expose this
    write endpoint to anonymous callers.

    Request body:
        {
          "message": "ReferenceError: foo is not defined",
          "stack":   "...",
          "url":     "https://app.example.com/projects/abc",
          "userAgent": "Mozilla/5.0 ...",
          "timestamp": "2026-05-01T10:23:44.123Z"
        }
    """
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip() or "<empty>"
    stack = (payload.get("stack") or "").strip()
    url = (payload.get("url") or "").strip()
    user_agent = (payload.get("userAgent") or "").strip()
    user_id = getattr(g, "user_id", "anonymous")

    # Truncate to keep the log file from being abused as bulk storage.
    # Caps are conservative — a real browser error rarely exceeds these.
    if len(message) > 1000:
        message = message[:1000] + "…(truncated)"
    if len(stack) > 4000:
        stack = stack[:4000] + "\n…(truncated)"
    if len(url) > 500:
        url = url[:500] + "…"
    if len(user_agent) > 200:
        user_agent = user_agent[:200]

    summary = (
        f"[CLIENT user={user_id} url={url} ua={user_agent[:80]}] {message}"
    )
    if stack:
        summary += f"\n{stack}"

    # Use the dedicated frontend-error logger so reviewers can grep [CLIENT]
    # and trace which user / route surfaced the error.
    logging.getLogger("client.error").error(summary)

    # Don't leak whether anything specific happened — keep the response
    # minimal so a malicious script can't probe via response shape.
    return jsonify({"success": True}), 200
