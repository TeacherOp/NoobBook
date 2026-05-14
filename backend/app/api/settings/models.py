"""
Model settings endpoints - Admin-configurable Claude model per use case.

Educational Note: Every prompt config has a baked-in model (Haiku, Sonnet, or
Opus). This endpoint lets an admin override those models per category:

    - chat:       main conversation, auto-naming, memory
    - studio:     all content generation (audio, video, presentations, etc.)
    - query:      database/csv/freshdesk analyzer agents
    - extraction: background source processing (PDF, PPTX, image, CSV)

Selecting "Default" (null) for a category clears the override so each prompt's
own JSON-baked model is used — preserving intentional per-prompt tuning like
presentation_agent=Opus.

Overrides are stored as env vars in .env (same pattern as ANTHROPIC_TIER) and
picked up on the next request via the PromptConfig dict subclass that resolves
"model" dynamically.

Routes:
- GET  /settings/models - Current overrides + available models + categories
- POST /settings/models - Set or clear overrides
"""
from flask import jsonify, request, current_app

from app.api.settings import settings_bp
from app.config import (
    AVAILABLE_MODELS,
    MODEL_CATEGORIES,
    get_current_settings,
    get_all_default_models,
)
from app.services.app_settings import EnvService
from app.services.auth.rbac import require_admin

env_service = EnvService()


@settings_bp.route('/settings/models', methods=['GET'])
@require_admin
def get_model_settings():
    """
    Return current per-category model overrides plus the lists needed to
    render the admin UI.

    Response:
        {
            "success": true,
            "settings": {
                "chat": "claude-opus-4-7" | null,
                "studio": "claude-haiku-4-5-20251001" | null,
                "query": null,
                "extraction": null
            },
            "available_models": [
                {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", ...},
                ...
            ],
            "categories": [
                {"id": "chat", "label": "Chat", "description": "...", "env_var": "CHAT_MODEL_OVERRIDE"},
                ...
            ]
        }
    """
    try:
        # `defaults` shows what each prompt actually resolves to when its
        # category is set to "Default" — used by the UI to make Default
        # honest about which models will be used (e.g. chat = mostly Sonnet
        # but Haiku for chat_naming/memory).
        defaults = get_all_default_models()
        return jsonify({
            'success': True,
            'settings': get_current_settings(),
            'available_models': list(AVAILABLE_MODELS.values()),
            'categories': list(MODEL_CATEGORIES.values()),
            'defaults': defaults,
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting model settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/settings/models', methods=['POST'])
@require_admin
def update_model_settings():
    """
    Update per-category model overrides.

    Request body:
        {
            "chat": "claude-opus-4-7",          // set override
            "studio": null,                      // clear override (use Default)
            "query": "claude-haiku-4-5-20251001",
            "extraction": null
        }

    Only categories present in the body are updated. Sending null or "" clears
    the override for that category. Unknown categories or invalid model ids
    return 400 without changing any values.
    """
    try:
        data = request.get_json()
        if data is None or not isinstance(data, dict):
            return jsonify({
                'success': False,
                'error': 'Request body must be a JSON object mapping category → model id or null'
            }), 400

        # Validate everything before writing anything so a single bad entry
        # doesn't leave the .env in a half-updated state.
        validated: dict[str, str] = {}
        for category, model_id in data.items():
            if category not in MODEL_CATEGORIES:
                return jsonify({
                    'success': False,
                    'error': f"Unknown category: {category}. Must be one of: {list(MODEL_CATEGORIES.keys())}"
                }), 400

            if model_id in (None, ""):
                validated[category] = ""  # empty string = clear override
                continue

            if not isinstance(model_id, str) or model_id not in AVAILABLE_MODELS:
                return jsonify({
                    'success': False,
                    'error': f"Invalid model for {category}: {model_id}. Must be one of: {list(AVAILABLE_MODELS.keys())}"
                }), 400

            validated[category] = model_id

        # Apply all validated updates
        for category, value in validated.items():
            env_var = MODEL_CATEGORIES[category]["env_var"]
            env_service.set_key(env_var, value)
            current_app.logger.info(
                "Updated %s to %r", env_var, value or "<cleared>"
            )

        # Reload .env so the new values are visible to os.environ immediately
        env_service.reload_env()

        return jsonify({
            'success': True,
            'message': 'Model settings updated successfully',
            'settings': get_current_settings(),
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error updating model settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
