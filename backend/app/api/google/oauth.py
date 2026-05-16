"""
Google OAuth 2.0 flow endpoints.

Educational Note: OAuth 2.0 is the industry standard for authorization.
It allows users to grant our app access to their Google Drive without
sharing their password.

The OAuth Dance:
1. /google/status  - Check if we're configured and connected
2. /google/auth    - Get the authorization URL (includes user_id in state)
3. (User visits Google, grants permission)
4. /google/callback - Google redirects here with auth code + state (user_id)
5. /google/disconnect - Remove stored tokens

Security Considerations:
- Never expose client secret to frontend
- Use HTTPS in production for callback URL
- Store refresh tokens securely in Supabase (per-user)
- Handle token expiration gracefully
- State parameter carries user_id for multi-user support

Routes:
- GET  /google/status     - Check configuration and connection
- GET  /google/auth       - Get OAuth authorization URL
- GET  /google/callback   - Handle OAuth callback (redirects)
- POST /google/disconnect - Remove stored tokens
"""
import html
import json
from typing import Optional
from flask import jsonify, request, current_app, make_response
from app.api.google import google_bp
from app.services.integrations.google import google_auth_service
from app.services.integrations.google.oauth_state import verify_state
from app.services.auth.rbac import get_request_identity


def _render_callback_page(status: str, message: str = ''):
    """
    Render the OAuth completion page.

    The callback is loaded inside a popup opened by the frontend's
    `useGoogleConnect` hook. The page posts the result back to the
    opener and self-closes; the opener's existing status poll is the
    fallback if the browser blocks postMessage or window.close().

    Origins for postMessage come from `CORS_ALLOWED_ORIGINS` so the
    completion event is delivered to whichever frontend host the operator
    has configured (works for local dev, Docker, and prod transparently).
    Falls back to `*` when no origins are configured — acceptable because
    the payload carries no secret material, just a status flag the opener
    re-validates via `/google/status`.
    """
    message_safe = html.escape(message)
    title = 'Google Drive connected' if status == 'success' else 'Google Drive sign-in failed'
    fallback_copy = 'You can close this window.' if status == 'success' else 'Please try again from the app.'
    origins = [o for o in (current_app.config.get('CORS_ALLOWED_ORIGINS') or []) if o and o.strip()] or ['*']
    payload = {'type': 'noobbook:google-auth', 'status': status, 'message': message}

    # JSON-escape, then neutralize sequences that could break out of the
    # inline <script> tag. Without this, a `message` from Google's `error`
    # query string containing `</script>` would close the script element
    # mid-stream and execute attacker-controlled HTML. Belt-and-braces:
    # the `message` is also html-escaped above for the visible <p> tag.
    def _js_literal(obj):
        return (
            json.dumps(obj)
            .replace('</', '<\\/')
            .replace(' ', '\\u2028')
            .replace(' ', '\\u2029')
        )

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Google Drive</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;background:#f5f1eb;color:#1c1917;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:24px}}.card{{max-width:380px}}.muted{{color:#78716c;font-size:14px;margin-top:8px}}</style>
</head><body><div class="card">
<h2>{html.escape(title)}</h2>
<p class="muted">{message_safe or html.escape(fallback_copy)}</p>
</div>
<script>
(function () {{
  var payload = {_js_literal(payload)};
  var origins = {_js_literal(origins)};
  try {{
    if (window.opener && !window.opener.closed) {{
      origins.forEach(function (o) {{
        try {{ window.opener.postMessage(payload, o); }} catch (e) {{}}
      }});
    }}
  }} catch (e) {{}}
  // Give the opener a tick to receive the message before closing.
  setTimeout(function () {{ try {{ window.close(); }} catch (e) {{}} }}, 200);
}})();
</script>
</body></html>"""

    response = make_response(body, 200 if status == 'success' else 400)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'no-store'
    return response


def _get_current_user_id() -> Optional[str]:
    """
    Get the current user ID from the authenticated session.

    Educational Note: In single-user mode (service key), this returns None
    which triggers the fallback to the default user in the database.
    For multi-user mode, implement JWT/session extraction here.

    Returns:
        User ID string or None for default user
    """
    identity = get_request_identity()
    if identity.is_authenticated:
        return identity.user_id
    return None


@google_bp.route('/google/status', methods=['GET'])
def google_status():
    """
    Check Google Drive configuration and connection status.

    Educational Note: This endpoint checks two things:
    1. Is Google OAuth configured? (client ID + secret set in .env)
    2. Is user connected? (valid tokens stored in Supabase users.google_tokens)

    Returns:
        {
            "success": true,
            "configured": true,   # OAuth credentials exist
            "connected": true,    # Valid tokens stored
            "email": "user@gmail.com"  # User's email if connected
        }
    """
    try:
        user_id = _get_current_user_id()
        is_configured = google_auth_service.is_configured()
        is_connected, email = google_auth_service.is_connected(user_id=user_id)

        return jsonify({
            'success': True,
            'configured': is_configured,
            'connected': is_connected,
            'email': email
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error checking Google status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@google_bp.route('/google/auth', methods=['GET'])
def google_auth():
    """
    Start Google OAuth flow by returning the authorization URL.

    Educational Note: The authorization URL contains:
    - client_id: Identifies our app to Google
    - redirect_uri: Where to send user after granting permission
    - scope: What permissions we're requesting (drive.readonly)
    - access_type=offline: Request a refresh token
    - prompt=consent: Always show consent screen (ensures refresh token)

    The frontend will redirect user to this URL.
    After user grants permission, Google redirects back to our callback.

    Returns:
        { "success": true, "auth_url": "https://accounts.google.com/..." }
    """
    try:
        if not google_auth_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'Google OAuth not configured. Please add Client ID and Secret in Admin Settings.'
            }), 400

        user_id = _get_current_user_id()
        auth_url = google_auth_service.get_auth_url(user_id=user_id)
        if not auth_url:
            return jsonify({
                'success': False,
                'error': 'Failed to generate auth URL'
            }), 500

        return jsonify({
            'success': True,
            'auth_url': auth_url
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error generating auth URL: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@google_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """
    Handle OAuth callback from Google.

    Educational Note: This is where the OAuth "dance" completes:
    1. Google redirects here with ?code=AUTHORIZATION_CODE&state=USER_ID
    2. We exchange the code for access + refresh tokens
    3. Tokens are stored in Supabase users.google_tokens (per-user)
    4. We redirect user back to frontend with success/error

    Why redirect instead of JSON response?
    - This endpoint is called by Google's redirect, not our frontend
    - User's browser is at accounts.google.com when they click "Allow"
    - We need to send them back to our app with a visual confirmation

    Query Params:
        code: Authorization code from Google (on success)
        state: User ID passed from get_auth_url (for multi-user support)
        error: Error message if user denied access

    Returns:
        Redirect to frontend with ?google_auth=success or ?google_auth=error
    """
    try:
        # Check for error (user denied access)
        oauth_error = request.args.get('error')
        if oauth_error:
            current_app.logger.warning("Google OAuth denied: %s", oauth_error)
            return _render_callback_page('error', oauth_error)

        # Get authorization code
        code = request.args.get('code')
        if not code:
            return _render_callback_page('error', 'No authorization code')

        # Verify the HMAC-signed state. Failures here mean the request
        # didn't come from a flow we minted — treat as adversarial and
        # bail before exchanging the code (otherwise we'd happily link
        # the attacker's Google account to whatever user_id they put in
        # the raw state). Replay protection is built into verify_state.
        raw_state = request.args.get('state') or None
        state_ok, user_id, state_err = verify_state(raw_state)
        if not state_ok:
            current_app.logger.warning("Google OAuth rejected: %s", state_err)
            return _render_callback_page('error', 'Invalid sign-in request')

        # Exchange code for tokens, passing user_id for storage
        success, message = google_auth_service.handle_callback(code, user_id=user_id)

        if success:
            current_app.logger.info("Google OAuth successful: %s", message)
            return _render_callback_page('success', message)

        current_app.logger.error("Google OAuth failed: %s", message)
        return _render_callback_page('error', message)

    except Exception as e:
        current_app.logger.error("Error in Google callback: %s", e)
        return _render_callback_page('error', str(e))


@google_bp.route('/google/disconnect', methods=['POST'])
def google_disconnect():
    """
    Disconnect Google Drive by removing stored tokens.

    Educational Note: This removes tokens from Supabase users.google_tokens.
    User will need to re-authenticate to use Google Drive again.

    Note: This does NOT revoke access at Google's end - user can
    manually revoke at https://myaccount.google.com/permissions

    Returns:
        { "success": true, "message": "Disconnected successfully" }
    """
    try:
        user_id = _get_current_user_id()
        success, message = google_auth_service.disconnect(user_id=user_id)

        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 500

    except Exception as e:
        current_app.logger.error(f"Error disconnecting Google: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
