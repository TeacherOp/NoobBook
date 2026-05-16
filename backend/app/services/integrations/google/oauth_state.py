"""
Signed OAuth `state` parameter for the Google Drive flow.

Why this exists
---------------
Before this module, `state` was just the raw `user_id` string. That made
the callback trivially CSRF-able: an attacker who knew (or guessed) the
target user's UUID could land them on a Google OAuth URL whose callback
stored the *attacker's* refresh token under the *victim's* row. RFC 6749
§10.12 says don't do that.

What we do now
--------------
- `state = base64url(payload).base64url(hmac)` where payload is a tiny
  JSON object `{u: user_id, n: nonce, e: exp_unix}` and hmac is computed
  with SECRET_KEY.
- Nonce is a random token. We persist issued nonces in the Supabase
  `oauth_state_nonces` table so each one is single-use AND the mint
  and verify can land on different gunicorn workers — the in-process
  dict version of this module deadlocked multi-worker deployments.
- Verification checks: HMAC integrity, exp not in the past, nonce was
  issued by us AND hasn't been consumed yet (atomic DELETE...RETURNING
  in Supabase). If any of those fail we treat the callback as
  adversarial and refuse the exchange.

Server-restart behaviour
------------------------
Persistent storage means OAuth flows that straddle a deploy/restart
still verify cleanly — the nonce row outlives any single process. Rows
older than the 10-minute TTL are pruned opportunistically on each
`sign_state()` call so the table self-cleans.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# 10 minutes — the gap between minting the URL and the user clicking
# Allow in Google's consent screen. Longer windows widen the replay
# surface; shorter windows kick out users who think before clicking.
STATE_TTL_SECONDS = 600

_TABLE = "oauth_state_nonces"


def _supabase():
    """Lazy import so importing this module at app boot doesn't pull
    the whole supabase package (avoids a circular init in tests)."""
    from app.services.integrations.supabase import get_supabase
    return get_supabase()


def _secret_key_bytes() -> bytes:
    """SECRET_KEY from env, encoded for HMAC. Falls back to the dev
    placeholder so unit tests work without a configured environment;
    production config rejects boot without SECRET_KEY set."""
    return os.getenv("SECRET_KEY", "dev-secret-key-change-in-production").encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    # Re-pad before decoding — urlsafe_b64decode requires correct '=' padding.
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))


def _prune_expired() -> None:
    """Best-effort cleanup of stale nonces. Runs on every issue so the
    table self-cleans without a separate cron. Errors are swallowed
    because pruning is a tidiness concern, not a correctness one."""
    cutoff = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() - STATE_TTL_SECONDS),
    )
    try:
        _supabase().table(_TABLE).delete().lt("created_at", cutoff).execute()
    except Exception as exc:
        logger.warning("oauth nonce prune failed (non-fatal): %s", exc)


def _issue_nonce(user_id: str) -> str:
    """Mint a fresh nonce and persist it. Caller signs the resulting
    payload immediately so we don't carry per-mint state in process."""
    nonce = secrets.token_urlsafe(18)
    _supabase().table(_TABLE).insert(
        {"nonce": nonce, "user_id": user_id}
    ).execute()
    _prune_expired()
    return nonce


class InvalidUserIdError(ValueError):
    """Raised when sign_state is called without a real user_id to bind
    the OAuth flow to. Surfaces to /google/auth as a 400 so the
    frontend can prompt the user to sign in first instead of letting
    PostgREST 500 on the `UUID NOT NULL` constraint."""


def _consume_nonce(nonce: str) -> bool:
    """Atomically claim a nonce. Returns True if the row existed (we
    just deleted it; valid first-use), False if it didn't (replay or
    unknown). Postgres DELETE...RETURNING via PostgREST returns the
    deleted rows in `response.data` — empty list means no match."""
    response = (
        _supabase()
        .table(_TABLE)
        .delete()
        .eq("nonce", nonce)
        .execute()
    )
    rows = response.data or []
    return bool(rows)


def sign_state(user_id: str) -> str:
    """Mint an HMAC-signed, nonce-protected `state` value for the auth URL.

    `user_id` must be a non-empty UUID string — the persistent nonce row
    has a `UUID NOT NULL` column, and there's no semantically meaningful
    OAuth flow without a real user to attribute the token to. Single-user
    deployments with an empty users table hit this branch; the caller
    should propagate it as a 400 so the frontend prompts for sign-in
    instead of silently 500-ing on the constraint.
    """
    if not user_id:
        raise InvalidUserIdError("sign_state requires a non-empty user_id")
    now = int(time.time())
    nonce = _issue_nonce(user_id)
    payload = json.dumps(
        {"u": user_id, "n": nonce, "e": now + STATE_TTL_SECONDS},
        separators=(",", ":"),
    ).encode("utf-8")
    sig = hmac.new(_secret_key_bytes(), payload, hashlib.sha256).digest()
    return f"{_b64url_encode(payload)}.{_b64url_encode(sig)}"


def verify_state(state: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """Return (ok, user_id, error_reason).

    Errors are short, non-leaky strings safe to surface to the user via
    the callback page. The caller logs the full reason on the server
    side already.
    """
    if not state or "." not in state:
        return False, None, "missing or malformed state"

    try:
        payload_b64, sig_b64 = state.split(".", 1)
        payload_raw = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)
    except Exception:
        return False, None, "malformed state encoding"

    expected_sig = hmac.new(_secret_key_bytes(), payload_raw, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, sig):
        return False, None, "state signature mismatch"

    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return False, None, "state payload not json"

    user_id = payload.get("u")
    nonce = payload.get("n")
    exp = payload.get("e")
    if not isinstance(user_id, str) or not isinstance(nonce, str) or not isinstance(exp, int):
        return False, None, "state payload incomplete"

    now = int(time.time())
    if now > exp:
        return False, None, "state expired"

    # Atomic single-use claim via Postgres DELETE. If no row was
    # deleted, the nonce was either replayed, expired and pruned, or
    # never issued by us — all three are rejection cases.
    try:
        consumed = _consume_nonce(nonce)
    except Exception as exc:
        logger.warning("oauth nonce consume failed: %s", exc)
        return False, None, "state store unavailable"

    if not consumed:
        return False, None, "state replayed or unknown"

    return True, user_id, None
