"""Saved Insights blueprint — auto-refreshing chat prompts."""
from flask import Blueprint

insights_bp = Blueprint("insights", __name__)

from app.api.insights import routes  # noqa: E402,F401  -- registers routes
