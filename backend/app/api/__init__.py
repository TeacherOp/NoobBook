"""
API Blueprint initialization.

Educational Note: Blueprints help organize Flask applications by
grouping related routes together. This makes the code more modular
and easier to maintain.

Blueprint Architecture:
- api_bp: Main API blueprint (registered at /api/v1 in app factory)
  - projects_bp: Project CRUD, costs, memory
  - chats_bp: Chat CRUD operations
  - messages_bp: Message sending (AI interaction)
  - prompts_bp: System prompt management
  - google_bp: Google Drive OAuth and file operations
  - transcription_bp: ElevenLabs speech-to-text config
  - settings_bp: API keys and processing tier config
  - sources_bp: Source upload, processing, citations
  - studio_bp: Studio management and collaboration

Nested blueprints are registered without url_prefix since routes
already include full paths like '/projects/<id>/chats'.
"""
from flask import Blueprint

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

# =============================================================================
# Register Nested Blueprints (Modular)
# =============================================================================
# These blueprints have their own folders with __init__.py and routes.py

from app.api.chats import chats_bp
from app.api.messages import messages_bp
from app.api.prompts import prompts_bp
from app.api.google import google_bp
from app.api.projects import projects_bp
from app.api.transcription import transcription_bp
from app.api.settings import settings_bp
from app.api.sources import sources_bp
from app.api.studio import studio_bp

# Register nested blueprints with the main api blueprint
# No url_prefix needed - routes already have full paths
api_bp.register_blueprint(chats_bp)
api_bp.register_blueprint(messages_bp)
api_bp.register_blueprint(prompts_bp)
api_bp.register_blueprint(google_bp)
api_bp.register_blueprint(projects_bp)
api_bp.register_blueprint(transcription_bp)
api_bp.register_blueprint(settings_bp)
api_bp.register_blueprint(sources_bp)
api_bp.register_blueprint(studio_bp)
