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
from flask import Blueprint, request, jsonify, g

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

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
