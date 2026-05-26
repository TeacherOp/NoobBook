"""
ElevenLabs transcription configuration endpoints.

Educational Note: These endpoints provide configuration for real-time
speech-to-text. The actual transcription happens client-side via WebSocket
for lowest latency - we just provide the secure connection details.

Why Client-Side WebSocket?
- Latency: Audio goes directly to ElevenLabs, not through our server
- Scalability: Our server doesn't need to handle audio streaming
- Cost: No bandwidth costs for audio passing through our server

Token-Based Authentication:
- ElevenLabs provides single-use tokens via their REST API
- Token is embedded in WebSocket URL: wss://api.elevenlabs.io/...?token=XXX
- Token expires after 15 minutes
- Frontend requests new token for each recording session

Routes:
- GET /transcription/config - Get WebSocket URL with fresh token
- GET /transcription/status - Check if ElevenLabs is configured
"""
from flask import jsonify, current_app, request
from app.api.transcription import transcription_bp
from app.services.integrations.elevenlabs import TranscriptionService
from app.services.ai_services.voice_polish_service import voice_polish_service

# Initialize service (lazy loads API key from env)
transcription_service = TranscriptionService()


@transcription_bp.route('/transcription/config', methods=['GET'])
def get_transcription_config():
    """
    Get ElevenLabs configuration for real-time transcription.

    Educational Note: This endpoint generates a single-use token and embeds it
    in the WebSocket URL. The flow is:

    1. Frontend calls this endpoint before recording
    2. We call ElevenLabs API to get single-use token
    3. We return WebSocket URL with token embedded
    4. Frontend connects directly to ElevenLabs WebSocket
    5. Token expires after 15 minutes (request fresh for each session)

    Security Note: The API key never leaves the server. Only the single-use
    token is embedded in the WebSocket URL for authentication. This is a
    common pattern for protecting API credentials while enabling client-side
    real-time features.

    Returns:
        {
            "success": true,
            "websocket_url": "wss://api.elevenlabs.io/v1/...?token=XXX",
            "model_id": "scribe_v1",
            "sample_rate": 16000,
            "encoding": "pcm_s16le"
        }
    """
    try:
        # Frontend can bias recognition by passing one or more
        # `keyterms` params (repeatable in the query string, or a single
        # comma-separated value as a fallback for clients that can't
        # repeat params). Sanitization + caps happen service-side.
        keyterms = request.args.getlist('keyterms')
        if not keyterms:
            raw = request.args.get('keyterms')
            if raw:
                keyterms = [t for t in raw.split(',') if t.strip()]

        config = transcription_service.get_elevenlabs_config(keyterms=keyterms)

        return jsonify({
            'success': True,
            **config
        }), 200

    except ValueError as e:
        # API key not configured
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        current_app.logger.error(f"Error getting transcription config: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get transcription configuration'
        }), 500


@transcription_bp.route('/transcription/status', methods=['GET'])
def get_transcription_status():
    """
    Check if ElevenLabs transcription is configured.

    Educational Note: This is a lightweight "health check" endpoint.
    It checks if the ElevenLabs API key is set without:
    - Exposing the actual key
    - Making any external API calls
    - Generating tokens (which have limited uses)

    Use Case: Frontend can call this on load to decide whether to
    show/hide the microphone button. No point showing voice input
    if transcription isn't configured.

    Returns:
        {
            "success": true,
            "configured": true  // or false if API key not set
        }
    """
    try:
        is_configured = transcription_service.is_configured()

        return jsonify({
            'success': True,
            'configured': is_configured
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error checking transcription status: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to check transcription status'
        }), 500


@transcription_bp.route('/transcription/polish', methods=['POST'])
def polish_transcript():
    """
    Final cleanup pass for a voice transcript.

    Runs Haiku with a tight prompt to strip residual fillers, false
    starts, and stuttering repetitions that ElevenLabs' `no_verbatim`
    flag didn't catch. Preserves meaning, tone, and technical terms.
    Returns the original text unchanged on any error so the UI can
    fall back safely.

    Body:
        { "text": "...", "project_id": "..." (optional) }
    Returns:
        { "success": true, "cleaned": "..." }
    """
    try:
        payload = request.get_json(silent=True) or {}
        text = (payload.get('text') or '').strip()
        if not text:
            return jsonify({'success': True, 'cleaned': ''}), 200

        project_id = payload.get('project_id') or None
        user_id = payload.get('user_id') or None

        cleaned = voice_polish_service.polish(
            text=text,
            project_id=project_id,
            user_id=user_id,
        )
        return jsonify({'success': True, 'cleaned': cleaned}), 200

    except Exception as e:
        current_app.logger.error(f"Error polishing transcript: {e}")
        # Surface the failure so the frontend can decide to use raw,
        # but never propagate a 500 that breaks the input box.
        return jsonify({
            'success': False,
            'error': 'Failed to polish transcript',
        }), 500
