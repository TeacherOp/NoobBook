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
- Nonce is a 16-byte random token. We track issued nonces in a
  process-local set so each one is single-use; a captured state can't
  be replayed within its (10 min) window.
- Verification checks: HMAC integrity, exp not in the past, nonce was
  issued by THIS process AND hasn't been consumed yet. If any of those
  fail we treat the callback as adversarial and refuse the exchange.

Server-restart behaviour
------------------------
The nonce set lives in memory. On Coolify redeploy / proxy bounce / OOM
the set is empty, so OAuth flows that started before the restart and
finished after will hard-fail verification. The user just clicks
Connect again. We considered persisting nonces in Supabase but the
restart window is short and the failure mode is graceful (retry).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Optional, Tuple

# 10 minutes — the gap between minting the URL and the user clicking
# Allow in Google's consent screen. Longer windows widen the replay
# surface; shorter windows kick out users who think before clicking.
STATE_TTL_SECONDS = 600

# Cap how many nonces we'll remember to bound memory. At one flow per
# user per ~minute this would take ~5h of sustained traffic to fill;
# the periodic prune below keeps real-world usage well below this.
_NONCE_CAP = 4096

_nonce_lock = threading.Lock()
# nonce -> issued_at unix timestamp. We remove on use (single-use) and
# prune expired entries on every read so the set self-cleans.
_issued_nonces: dict[str, int] = {}


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


def _prune_expired(now: int) -> None:
    """Drop nonces past their TTL. Cheap enough to run on every issue/check."""
    expired = [n for n, t in _issued_nonces.items() if now - t > STATE_TTL_SECONDS]
    for n in expired:
        _issued_nonces.pop(n, None)


def sign_state(user_id: str) -> str:
    """Mint an HMAC-signed, nonce-protected `state` value for the auth URL."""
    now = int(time.time())
    nonce = secrets.token_urlsafe(12)

    with _nonce_lock:
        _prune_expired(now)
        # Hard cap. Drop the oldest to make room rather than fail issuance
        # — under attack we'd rather rotate old in-flight flows than reject
        # legitimate users who happen to click Connect during a flood.
        if len(_issued_nonces) >= _NONCE_CAP:
            oldest = sorted(_issued_nonces.items(), key=lambda kv: kv[1])[0][0]
            _issued_nonces.pop(oldest, None)
        _issued_nonces[nonce] = now

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

    # Single-use: pop the nonce. If it isn't in the set, the state was
    # either replayed, minted by a since-restarted process, or never
    # issued by us at all — all three are rejection cases.
    with _nonce_lock:
        _prune_expired(now)
        if nonce not in _issued_nonces:
            return False, None, "state replayed or unknown"
        _issued_nonces.pop(nonce, None)

    return True, user_id, None
