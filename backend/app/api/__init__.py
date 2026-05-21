"""
API Blueprint initialization.

Educational Note: Blueprints help organize Flask applications by
grouping related routes together. This makes the code more modular
and easier to maintain.

Blueprint Architecture:
- api_bp: Main API blueprint (registered at /api/v1 in app factory)
  - auth_bp: Authentication (signup, login, logout, session)
  - projects_bp: Project CRUD, costs, memory
  - chats_bp: Chat CRUD operations
  - messages_bp: Message sending (AI interaction)
  - prompts_bp: System prompt management
  - google_bp: Google Drive OAuth and file operations
  - transcription_bp: ElevenLabs speech-to-text config
  - settings_bp: API keys and processing tier config
  - sources_bp: Source upload, processing, citations
  - studio_bp: Studio management and collaboration
  - brand_bp: Brand assets and configuration

Authentication: A before_request hook on api_bp validates JWT tokens
for ALL routes except /auth/* endpoints. This protects every endpoint
without needing @require_auth on each route.
"""
import logging
import re
import time
import uuid

from flask import Blueprint, request, jsonify, g

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)

# =============================================================================
# Request-ID + timing middleware (§1.4 + §1.5)
# =============================================================================
# Every request gets a UUID-shaped correlation ID. The frontend axios client
# generates one via `crypto.randomUUID()` and sends it as `X-Request-Id`; if
# absent we mint one server-side. The ID is stamped onto every log record by
# `_RequestIdFilter` in `app/utils/logger.py` so a frontend bug report
# (containing the req_id from DevTools) can be grepped directly in
# backend.log. The ID is also echoed back in the response so the frontend can
# print it.
#
# Run BEFORE `authenticate_request` so even unauthenticated requests (a 401
# from `before_request` itself) carry a req_id — which is exactly the case we
# need most often when debugging spontaneous logouts.

_REQ_ID_HEADER = "X-Request-Id"
# Strict allowlist: hex / alphanumeric / dash / underscore only. Anything
# else gets rejected and we mint a fresh server-side ID. Without this, a
# malicious client could pass `abc]: spoofed-log-line [req:fake` and inject
# fake log content via the format-string interpolation (the M2 finding from
# code-review). 1..64 chars matches the previous max length.
_REQ_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Per-request lifecycle log allowlist. We deliberately skip the high-rate
# pollers (/active-tasks, /health, /auth/me) — those fire every few
# seconds and would otherwise dominate the file. Everything else that
# mutates state (POST/PUT/DELETE) or touches chats/sources/projects gets
# a REQ_START + REQ_DONE pair so a customer-reported turn is greppable
# end-to-end via the req_id.
_LIFECYCLE_SKIP_SUFFIXES = ("/active-tasks", "/health", "/auth/me")
_LIFECYCLE_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_LIFECYCLE_GET_PREFIXES = ("/chats", "/sources", "/projects", "/messages")


def _should_log_lifecycle(method: str, path: str) -> bool:
    """True if this request gets the REQ_START / REQ_DONE pair."""
    for suffix in _LIFECYCLE_SKIP_SUFFIXES:
        if path.endswith(suffix):
            return False
    if method in _LIFECYCLE_MUTATING_METHODS:
        return True
    if method == "GET":
        return any(seg in path for seg in _LIFECYCLE_GET_PREFIXES)
    return False


@api_bp.before_request
def _attach_request_id():
    """Mint or accept a per-request correlation ID and start the latency timer.

    Registered BEFORE `authenticate_request` so 401 responses still carry the
    req_id (the most common case we need to correlate).

    CORS preflights (OPTIONS) are skipped — they don't carry app-level
    semantics worth tracing and were producing noisy SLOW_REQUEST lines on
    cached preflight refreshes. Matches the OPTIONS-skip in
    `authenticate_request` below.
    """
    if request.method == 'OPTIONS':
        return None
    incoming = request.headers.get(_REQ_ID_HEADER, "").strip()
    if incoming and _REQ_ID_RE.fullmatch(incoming):
        g.req_id = incoming
    else:
        g.req_id = uuid.uuid4().hex[:16]  # 16 hex chars = 64 bits = plenty
    g._t0 = time.monotonic()

    if _should_log_lifecycle(request.method, request.path):
        # Short user prefix (first 8 hex of the UUID) keeps the line scannable
        # while still distinguishing users when the same path is hit by many.
        # Falls back to "-" before authenticate_request runs / for share routes.
        ua_user = getattr(g, "user_id", None)
        if ua_user:
            ua_user = str(ua_user)[:8]
        else:
            ua_user = "-"
        # Best-effort first IP from X-Forwarded-For; trim to 32 chars to
        # cover IPv6 without bloating the line.
        ip = (request.headers.get("X-Forwarded-For", "") or request.remote_addr or "").split(",")[0].strip()
        logger.info(
            "REQ_START method=%s path=%s user=%s ip=%s",
            request.method, request.path, ua_user, ip[:32],
        )


@api_bp.after_request
def _emit_request_id_and_timing(response):
    """Echo X-Request-Id back to the client and log slow paths (§1.5)."""
    req_id = getattr(g, "req_id", None)
    if req_id:
        response.headers[_REQ_ID_HEADER] = req_id

    t0 = getattr(g, "_t0", None)
    if t0 is not None:
        elapsed = time.monotonic() - t0
        # 1.0s threshold catches the failure modes we care about (DB connect
        # timeout, slow Claude calls, GoTrue blips) without flooding the log
        # with normal sub-second requests.
        if elapsed > 1.0:
            logger.warning(
                "SLOW_REQUEST method=%s path=%s status=%s elapsed=%.2fs",
                request.method, request.path, response.status_code, elapsed,
            )
        if _should_log_lifecycle(request.method, request.path):
            # Pair with REQ_START so a customer turn reads as one block
            # under the req_id. `len` is the response content length when
            # known; -1 if streaming / chunked so the lifecycle log still
            # makes sense for SSE endpoints.
            try:
                body_len = int(response.headers.get("Content-Length", -1))
            except (TypeError, ValueError):
                body_len = -1
            level_fn = logger.warning if elapsed >= 1.0 else logger.info
            level_fn(
                "REQ_DONE method=%s path=%s status=%s ms=%d len=%d",
                request.method, request.path, response.status_code,
                int(elapsed * 1000), body_len,
            )
    return response


# =============================================================================
# Authentication - Protect all routes except /auth/*
# =============================================================================
# Educational Note: before_request runs before every request to any route
# under api_bp. We skip auth endpoints (login, signup, refresh) since those
# are public. All other routes require a valid JWT token.

from app.utils.auth_middleware import validate_token  # noqa: E402

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker/Coolify — no auth required."""
    return {"status": "ok"}, 200


@api_bp.before_request
def authenticate_request():
    """Validate JWT for all API requests except auth endpoints."""
    # Skip CORS preflight requests — browser sends OPTIONS before authenticated requests
    if request.method == 'OPTIONS':
        return None

    # Skip authentication for auth and health routes
    if request.path.startswith('/api/v1/auth/') or request.path == '/api/v1/health':
        return None

    # Share viewer routes are token-gated, not JWT-gated. The
    # @require_share_token decorator validates the URL token and (for
    # invited mode) requires a JWT separately. Skipping the global JWT
    # check here is what makes public-mode share links work without a
    # logged-in viewer.
    if request.path.startswith('/api/v1/share/'):
        return None

    # Google's OAuth redirect lands here as a top-level browser GET with
    # no Authorization header (Google initiates it, the browser just
    # follows). The user is identified by the `state` query parameter
    # set when we minted the auth URL.
    if request.path == '/api/v1/google/callback':
        return None

    user_id = validate_token()

    if not user_id:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    # Attach user_id to request context for use in route handlers
    g.user_id = user_id
    return None


# =============================================================================
# Register Nested Blueprints (Modular)
# =============================================================================
# These blueprints have their own folders with __init__.py and routes.py

from app.api.auth import auth_bp
from app.api.chats import chats_bp
from app.api.messages import messages_bp
from app.api.prompts import prompts_bp
from app.api.google import google_bp
from app.api.projects import projects_bp
from app.api.transcription import transcription_bp
from app.api.settings import settings_bp
from app.api.sources import sources_bp
from app.api.studio import studio_bp
from app.api.brand import brand_bp
from app.api.share import share_bp
from app.api.logs import logs_bp
from app.api.insights import insights_bp
from app.api.debug import debug_bp

# Register nested blueprints with the main api blueprint
# No url_prefix needed - routes already have full paths
api_bp.register_blueprint(auth_bp)
api_bp.register_blueprint(chats_bp)
api_bp.register_blueprint(messages_bp)
api_bp.register_blueprint(prompts_bp)
api_bp.register_blueprint(google_bp)
api_bp.register_blueprint(projects_bp)
api_bp.register_blueprint(transcription_bp)
api_bp.register_blueprint(settings_bp)
api_bp.register_blueprint(sources_bp)
api_bp.register_blueprint(studio_bp)
api_bp.register_blueprint(brand_bp)
api_bp.register_blueprint(share_bp)
api_bp.register_blueprint(logs_bp)
api_bp.register_blueprint(insights_bp)
api_bp.register_blueprint(debug_bp)
