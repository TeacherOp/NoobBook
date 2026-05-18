"""
Auth Middleware - JWT validation for protected routes.

Educational Note: This middleware validates JWT tokens issued by Supabase Auth.
We keep using the SERVICE_KEY Supabase client for database queries (bypasses RLS),
but validate the user's JWT to extract their user_id. This is simpler than
switching to ANON_KEY and lets the backend act as a trusted server.

Validation strategy:
  1. **Local signature verification** (preferred) — when JWT_SECRET is configured
     in the backend env, we decode the JWT locally with PyJWT. No network call,
     microsecond-fast, immune to the cache-miss race that previously caused 7+
     parallel /auth/v1/user calls per dashboard load when many requests arrived
     before the first cache write.
  2. **Supabase Auth roundtrip** (fallback) — if JWT_SECRET isn't set, fall
     back to `supabase.auth.get_user(token)` (60s cached). This keeps dev
     workflows working when nobody's wired up the secret.

Pattern: Decorator-based auth, similar to Flask-Login but using Supabase JWTs.
"""
import functools
import logging
import os
import time
import threading
from typing import Optional, Dict, Tuple

import jwt
from flask import request, jsonify, g
from app.services.integrations.supabase import get_auth_verifier_client

logger = logging.getLogger(__name__)

# Read once at module load — env vars don't change between requests.
# Supabase signs JWTs with the same JWT_SECRET its Auth/Postgrest containers
# share via docker-compose. If the operator hasn't plumbed it through to the
# backend container, we fall back to the network-roundtrip path.
_JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SUPABASE_JWT_SECRET") or ""
# Default to "authenticated" — the audience claim Supabase puts on user JWTs.
_JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "authenticated")

if _JWT_SECRET:
    logger.info("Auth middleware: local JWT verification enabled")
else:
    logger.warning(
        "Auth middleware: JWT_SECRET not set — falling back to Supabase Auth "
        "roundtrip on every cache miss. Set JWT_SECRET on the backend container "
        "to eliminate redundant Kong calls."
    )

# ─── Token Validation Cache ─────────────────────────────────────────────────
# The cache serves two distinct purposes depending on whether local JWT
# verification is enabled:
#
# 1. Fast-path mode (JWT_SECRET set): local PyJWT verifies signature + exp on
#    every request (microseconds). The cache then tracks "we asked GoTrue
#    about this token within the last 60s" so we still catch token
#    revocation (sign-out, password change, admin force-revoke) within 60s
#    of the event, matching the original cache window — without paying the
#    Kong roundtrip on every request.
#
# 2. Slow-path mode (JWT_SECRET unset): cache tracks "we asked GoTrue about
#    this token within the last 60s and got user_id back". Saves repeated
#    Auth calls for cache-hit requests. Same as the historical behaviour.
#
# In both modes a per-token lock prevents the cache-miss stampede that used
# to fire 7+ identical /auth/v1/user calls when parallel requests arrived
# before the first cache write.
_token_cache: Dict[str, Tuple[str, float]] = {}  # {token: (user_id, expires_at)}
_TOKEN_CACHE_TTL = 60  # seconds — both fast-path revocation window and slow-path TTL
_cache_lock = threading.Lock()
_token_locks: Dict[str, threading.Lock] = {}


def _get_cached_user_id(token: str) -> Optional[str]:
    """Check if a token has a valid cached validation result."""
    cached = _token_cache.get(token)
    if cached:
        user_id, expires_at = cached
        if time.time() < expires_at:
            return user_id
        # Expired — remove from cache
        with _cache_lock:
            _token_cache.pop(token, None)
    return None


def _cache_token(token: str, user_id: str) -> None:
    """Cache a successful token validation result."""
    with _cache_lock:
        _token_cache[token] = (user_id, time.time() + _TOKEN_CACHE_TTL)
        # Prevent unbounded growth — evict expired entries when cache gets large
        if len(_token_cache) > 100:
            now = time.time()
            expired = [k for k, (_, exp) in _token_cache.items() if now >= exp]
            for k in expired:
                del _token_cache[k]
                _token_locks.pop(k, None)


def _get_or_create_token_lock(token: str) -> threading.Lock:
    """One lock per token. Ensures only one in-flight GoTrue revocation
    check per token at a time — without this, a cold cache hit by 7
    parallel requests would still fan out to 7 Kong calls."""
    with _cache_lock:
        lock = _token_locks.get(token)
        if lock is None:
            lock = threading.Lock()
            _token_locks[token] = lock
        return lock


def get_current_user_id() -> Optional[str]:
    """
    Get the authenticated user's ID from the request context.

    Must be called within a request that passed JWT validation
    (either via @require_auth or the before_request hook).

    Returns:
        User ID string or None if not authenticated
    """
    return getattr(g, 'user_id', None)


def validate_token() -> Optional[str]:
    """
    Validate the JWT from the Authorization header (or ?token= query param) and return the user_id.

    Returns:
        User ID string on success, None on failure

    Educational Note: We call supabase.auth.get_user(jwt) which contacts
    the Supabase Auth server to verify the token signature and expiration.
    The SERVICE_KEY client has permission to validate any user's token.

    Performance: Results are cached for 60 seconds to avoid redundant Auth
    server calls when multiple browser elements (images, videos) load
    simultaneously with the same token.

    Query param fallback: Browser elements like <img>, <video>, <audio>, and <iframe>
    can't send Authorization headers. For these, the frontend appends ?token=JWT
    to the URL. We only check the query param when no Authorization header is present.
    """
    auth_header = request.headers.get('Authorization', '')

    if auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Strip "Bearer "
    else:
        # Fallback: check query parameter for browser elements (img, video, iframe, etc.)
        token = request.args.get('token', '')

    if not token:
        logger.warning("No auth token found (header=%s, query=%s)", bool(auth_header), bool(request.args.get('token')))
        return None

    # Fast path: verify the JWT signature locally. Costs microseconds, no
    # network call. Requires JWT_SECRET in the backend env (the same
    # secret Supabase Auth/Postgrest already share).
    #
    # Revocation safety: local-verify alone extends the post-revocation
    # validity window to the full JWT lifetime (up to JWT_EXPIRY).
    # To match the prior 60s revocation window, we still call GoTrue
    # once per token per 60s — the call is deduplicated across parallel
    # requests via a per-token lock. Hot-path requests (within the 60s
    # window) skip the network call entirely and stay microsecond-fast.
    if _JWT_SECRET:
        try:
            claims = jwt.decode(
                token,
                _JWT_SECRET,
                algorithms=["HS256"],
                audience=_JWT_AUDIENCE,
            )
            user_id = claims.get("sub")
            if not user_id:
                logger.warning("JWT decoded but has no `sub` claim")
                return None
            user_id = str(user_id)

            # Recently verified against GoTrue? Trust local result.
            if _get_cached_user_id(token):
                return user_id

            # Stale (or never checked). Do a real GoTrue call to catch
            # revocation. Lock ensures parallel requests deduplicate to
            # one network call.
            lock = _get_or_create_token_lock(token)
            with lock:
                # Double-check after acquiring lock — another request may
                # have just refreshed the cache while we were waiting.
                if _get_cached_user_id(token):
                    return user_id
                try:
                    # Dedicated client: keeps gotrue's auth-event listener
                    # off the data singleton so a SIGNED_IN / TOKEN_REFRESHED
                    # firing during this verify call can't flip the
                    # singleton's postgrest Authorization header to a user
                    # JWT and 42501 every service-role-only RPC after.
                    supabase = get_auth_verifier_client()
                    response = supabase.auth.get_user(token)
                    if response and response.user:
                        _cache_token(token, user_id)
                        return user_id
                    # GoTrue says no — token has been revoked (sign-out,
                    # password change, admin force-revoke).
                    logger.info("Token revoked by GoTrue — denying access")
                    return None
                except Exception as e:
                    # GoTrue itself is unreachable (network blip, GoTrue
                    # restart). Fail-open: trust the locally-verified
                    # signature, refresh the cache so we retry the
                    # revocation check after the next 60s window. This
                    # matches the historical fail-open behaviour of the
                    # cache-hit path.
                    logger.warning(
                        "Revocation check failed (GoTrue unreachable: %s: %s) — "
                        "trusting local signature for the next %ds",
                        type(e).__name__, e, _TOKEN_CACHE_TTL,
                    )
                    _cache_token(token, user_id)
                    return user_id
        except jwt.ExpiredSignatureError:
            # Token is past its `exp`. Frontend's silent-refresh path will
            # exchange the refresh token and retry — no need to log noisily.
            return None
        except jwt.InvalidAudienceError:
            logger.warning("JWT audience mismatch (expected %s)", _JWT_AUDIENCE)
            return None
        except jwt.InvalidSignatureError:
            logger.warning("JWT signature mismatch — wrong JWT_SECRET on backend?")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("JWT decode failed: %s", e)
            return None
        except Exception as e:
            # Unexpected failure during local decode — fall through to the
            # network path so we don't lock anyone out from a library quirk.
            logger.warning("Local JWT decode raised %s: %s — falling back to Auth", type(e).__name__, e)

    # Slow path (no JWT_SECRET configured, or local decode hit an unexpected
    # exception): cache + Supabase Auth roundtrip. Same behaviour as before.
    cached_user_id = _get_cached_user_id(token)
    if cached_user_id:
        return cached_user_id

    try:
        # Same dedicated client as the fast-path slow-confirm above —
        # keeps the data singleton's identity pinned to service_role.
        supabase = get_auth_verifier_client()
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            logger.warning("Auth get_user returned no user")
            return None

        user_id = str(user_response.user.id)
        _cache_token(token, user_id)
        return user_id
    except Exception as e:
        logger.warning("Token validation failed: %s: %s", type(e).__name__, e)
        return None


def verify_project_access(project_id: str) -> Optional[tuple]:
    """
    Verify the current user owns the given project.

    Call at the top of any route that takes a project_id to prevent
    users from accessing other users' data (chats, sources, brand, etc.).

    Returns:
        None if the user owns the project.
        (jsonify error, 404) tuple if not — return this from the route.

    Usage:
        denied = verify_project_access(project_id)
        if denied:
            return denied
    """
    from app.services.data_services import project_service

    user_id = get_current_user_id()
    project = project_service.get_project(project_id, user_id=user_id)

    if not project:
        return jsonify({"success": False, "error": "Project not found"}), 404

    return None


def require_auth(f):
    """
    Decorator that requires a valid Supabase JWT in the Authorization header.

    Sets g.user_id on success. Returns 401 on failure.
    Use this for routes that need explicit auth (e.g., /auth/me, /auth/logout).
    Most routes are protected by the before_request hook in api/__init__.py instead.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = validate_token()

        if not user_id:
            return jsonify({"success": False, "error": "Authentication required"}), 401

        g.user_id = user_id
        return f(*args, **kwargs)

    return decorated
