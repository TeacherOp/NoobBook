"""
Google Auth Service - Handle Google OAuth 2.0 authentication flow.

Educational Note: This service manages the OAuth 2.0 flow for Google APIs:
1. Generate authorization URL (user visits to grant access)
2. Exchange authorization code for access/refresh tokens
3. Refresh access tokens when they expire (access tokens last ~1 hour)
4. Store tokens securely in Supabase (per-user)

OAuth 2.0 Flow:
    1. User clicks "Connect Google Drive"
    2. We redirect to Google's auth page with our client ID and scopes
    3. User grants permission
    4. Google redirects back with an authorization code
    5. We exchange the code for access + refresh tokens
    6. We store tokens in Supabase users table
    7. When access token expires, we use refresh token to get a new one

Required Setup:
    1. Create project at https://console.cloud.google.com
    2. Enable Google Drive API
    3. Create OAuth 2.0 credentials (Web application)
    4. Add the callback URL as a redirect URI. The URL is derived from your
       deployment's host + `<API_PREFIX>/google/callback` (e.g.
       `http://localhost:5001/api/v1/google/callback` for local dev or
       `https://your-domain.com/api/v1/google/callback` for prod). Override
       explicitly with the `GOOGLE_REDIRECT_URI` env var if needed.
    5. Copy Client ID and Client Secret to Admin Settings

Migration Note (2026-01):
    Previously tokens were stored in data/google_tokens.json (single file for all users).
    Now tokens are stored per-user in the Supabase users.google_tokens JSONB column,
    enabling proper multi-user support with isolated Google Drive connections.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from flask import current_app, has_request_context, request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

from app.services.integrations.google.oauth_state import sign_state
from app.services.integrations.supabase import get_supabase


class GoogleAuthService:
    """
    Service class for Google OAuth 2.0 authentication.

    Educational Note: This service handles the complete OAuth lifecycle:
    - Generating auth URLs with appropriate scopes
    - Exchanging auth codes for tokens
    - Refreshing expired tokens
    - Storing and loading credentials from Supabase
    """

    # OAuth scopes we need for Google Drive
    # Educational Note: Scopes define what access we're requesting
    # - drive.readonly: Read files from Drive
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
    ]

    # Default redirect URI used when no request context is available and
    # GOOGLE_REDIRECT_URI is not set (e.g. CLI invocations during tests).
    # In production the real value is resolved per-request from the active
    # host or the env override — see `_get_redirect_uri()`.
    DEFAULT_REDIRECT_URI = 'http://localhost:5001/api/v1/google/callback'

    def __init__(self):
        """Initialize the Google Auth service."""
        self._supabase = None

    def _get_redirect_uri(self) -> str:
        """
        Resolve the OAuth callback URI for the current deployment.

        Resolution order:
        1. `GOOGLE_REDIRECT_URI` env var (explicit operator override — must
           match exactly what's registered in Google Cloud Console).
        2. Derived from the active request's host + API prefix. Honors
           X-Forwarded-* headers via ProxyFix, so it works behind Coolify /
           Traefik / Kong without manual config.
        3. Localhost fallback for off-request contexts (tests, CLI).

        Google requires the redirect URI sent in `/auth` to match the one
        sent in the token exchange exactly, which is why both `get_auth_url`
        and `handle_callback` route through this single helper.
        """
        override = os.getenv('GOOGLE_REDIRECT_URI', '').strip()
        if override:
            return override

        if has_request_context():
            api_prefix = current_app.config.get('API_PREFIX', '/api/v1').rstrip('/')
            return f"{request.host_url.rstrip('/')}{api_prefix}/google/callback"

        return self.DEFAULT_REDIRECT_URI

    @property
    def supabase(self):
        """Lazy load Supabase client to avoid initialization issues."""
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase

    def _get_client_config(self) -> Optional[Dict[str, Any]]:
        """
        Get OAuth client configuration from environment.

        Educational Note: We build the client config dict that google-auth
        expects from our environment variables. This avoids needing a
        client_secrets.json file.

        Returns:
            Client config dict or None if credentials not set
        """
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

        if not client_id or not client_secret:
            return None

        return {
            'web': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [self._get_redirect_uri()],
            }
        }

    def _get_default_user_id(self) -> Optional[str]:
        """
        Get the default user ID for single-user mode.

        Educational Note: In single-user mode (using service key), we don't have
        a logged-in user context. We use the first user in the database as the
        default. For multi-user mode with proper auth, the user_id should be
        passed explicitly from the authenticated session.

        Returns:
            User ID string or None if no users exist
        """
        try:
            result = self.supabase.table("users").select("id").limit(1).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error("Error getting default user: %s", e)
            return None

    def is_configured(self) -> bool:
        """
        Check if Google OAuth credentials are configured.

        Returns:
            True if both client ID and secret are set
        """
        return self._get_client_config() is not None

    def is_connected(self, user_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if we have valid Google credentials for a user.

        Educational Note: This checks if:
        1. User has tokens stored in Supabase
        2. Tokens are valid or can be refreshed

        Args:
            user_id: Optional user ID. If not provided, uses default user (single-user mode)

        Returns:
            Tuple of (is_connected, user_email or None)
        """
        # Use get_credentials() which handles token refresh
        creds = self.get_credentials(user_id)
        if creds and creds.valid:
            # Try to get user info
            email = self._get_user_email(creds)
            return True, email
        return False, None

    def get_auth_url(self, user_id: Optional[str] = None) -> Optional[str]:
        """
        Generate the Google OAuth authorization URL.

        Educational Note: This URL is where users are redirected to grant
        permission. It includes:
        - client_id: Identifies our app
        - scope: What access we're requesting
        - redirect_uri: Where to send user after auth
        - access_type=offline: Request refresh token for long-term access
        - prompt=consent: Always show consent screen (ensures refresh token)
        - state: User ID for multi-user support (identifies who initiated OAuth)

        Args:
            user_id: Optional user ID to include in state parameter

        Returns:
            Authorization URL or None if not configured
        """
        client_config = self._get_client_config()
        if not client_config:
            return None

        # Use provided user_id or get default for single-user mode
        effective_user_id = user_id or self._get_default_user_id()

        # Refuse to mint a flow with no user attached. sign_state would
        # reject anyway (its UUID column is NOT NULL); returning None
        # here lets the route surface a clean 400 instead of a 500.
        if not effective_user_id:
            logger.warning("get_auth_url called with no user_id (no default user)")
            return None

        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=self._get_redirect_uri()
        )

        # Generate auth URL
        # access_type='offline' ensures we get a refresh token
        # prompt='consent' forces consent screen to ensure refresh token
        # state is HMAC-signed + nonce-protected so the callback can
        # verify it really came from a flow WE started (no CSRF where
        # someone tricks a victim into pasting an OAuth URL that links
        # the attacker's Google account to the victim's row).
        signed_state = sign_state(effective_user_id)
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true',
            state=signed_state,
        )

        return auth_url

    def handle_callback(self, authorization_code: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Handle the OAuth callback and exchange code for tokens.

        Educational Note: After user grants permission, Google redirects
        to our callback with an authorization code. We exchange this code
        for access and refresh tokens, then store them in Supabase.

        Args:
            authorization_code: The code from Google's redirect
            user_id: User ID from state parameter (for multi-user support)

        Returns:
            Tuple of (success, message or error)
        """
        client_config = self._get_client_config()
        if not client_config:
            return False, "Google OAuth not configured"

        # Use provided user_id or get default for single-user mode
        effective_user_id = user_id or self._get_default_user_id()
        if not effective_user_id:
            return False, "No user found to associate Google tokens with"

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=self.SCOPES,
                redirect_uri=self._get_redirect_uri()
            )

            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)

            # Get credentials object
            credentials = flow.credentials

            # Save credentials to Supabase
            self._save_credentials(credentials, effective_user_id)

            # Get user email for confirmation
            email = self._get_user_email(credentials)

            return True, f"Successfully connected as {email}" if email else "Successfully connected"

        except Exception as e:
            return False, f"Failed to authenticate: {str(e)}"

    def disconnect(self, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Disconnect Google account by removing stored tokens.

        Educational Note: We don't revoke the tokens (which would require
        an API call), we just delete them from Supabase. User can revoke
        access from their Google account settings if desired.

        Args:
            user_id: Optional user ID. If not provided, uses default user

        Returns:
            Tuple of (success, message)
        """
        effective_user_id = user_id or self._get_default_user_id()
        if not effective_user_id:
            return False, "No user found"

        try:
            # Set google_tokens to null in Supabase
            self.supabase.table("users").update(
                {"google_tokens": None}
            ).eq("id", effective_user_id).execute()

            return True, "Google Drive disconnected"
        except Exception as e:
            return False, f"Failed to disconnect: {str(e)}"

    def get_credentials(self, user_id: Optional[str] = None) -> Optional[Credentials]:
        """
        Get valid credentials, refreshing if necessary.

        Educational Note: This is the main method other services should use
        to get credentials for API calls. It handles:
        1. Loading saved credentials from Supabase
        2. Checking if they're expired
        3. Refreshing if needed
        4. Returning valid credentials or None

        Args:
            user_id: Optional user ID. If not provided, uses default user

        Returns:
            Valid Credentials object or None
        """
        effective_user_id = user_id or self._get_default_user_id()
        creds = self._load_credentials(effective_user_id)
        if not creds:
            return None

        # Check if credentials need refresh
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds, effective_user_id)
            except Exception as e:
                logger.warning("Failed to refresh Google credentials: %s", e)
                return None

        return creds if creds.valid else None

    def _load_credentials(self, user_id: Optional[str] = None) -> Optional[Credentials]:
        """
        Load credentials from Supabase for a user.

        Args:
            user_id: User ID to load credentials for

        Returns:
            Credentials object or None if not found/invalid
        """
        if not user_id:
            return None

        try:
            result = self.supabase.table("users").select("google_tokens").eq("id", user_id).execute()

            if not result.data or len(result.data) == 0:
                return None

            token_data = result.data[0].get("google_tokens")
            if not token_data:
                return None

            # Get client_id and client_secret from env vars, not from DB
            # Security: app credentials should never be stored in the database
            client_config = self._get_client_config()
            if not client_config:
                return None
            web_config = client_config['web']

            return Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=web_config['client_id'],
                client_secret=web_config['client_secret'],
                scopes=token_data.get('scopes')
            )
        except Exception as e:
            logger.error("Error loading Google credentials: %s", e)
            return None

    def _save_credentials(self, credentials: Credentials, user_id: str) -> None:
        """
        Save credentials to Supabase for a user.

        Educational Note: We only store user-specific tokens (access token,
        refresh token, scopes). App credentials (client_id, client_secret)
        are NOT stored in the database for security - they come from env vars.

        Args:
            credentials: The Credentials object to save
            user_id: User ID to save credentials for
        """
        # Get user email for reference
        email = self._get_user_email(credentials)

        # Only store user-specific tokens, NOT app credentials
        # Security: client_id and client_secret should only live in env vars
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'scopes': credentials.scopes,
            'google_email': email,
            'saved_at': datetime.now().isoformat()
        }

        try:
            self.supabase.table("users").update(
                {"google_tokens": token_data}
            ).eq("id", user_id).execute()
        except Exception as e:
            logger.error("Error saving Google credentials to Supabase: %s", e)
            raise

    def _get_user_email(self, credentials: Credentials) -> Optional[str]:
        """
        Get the email of the authenticated user.

        Educational Note: We use Drive API's "about" endpoint to get user info.
        This works with our drive.readonly scope (unlike oauth2 userinfo which
        requires a separate userinfo.email scope).

        Args:
            credentials: Valid credentials

        Returns:
            User email or None
        """
        try:
            from googleapiclient.discovery import build

            # Use Drive API to get user email (works with drive.readonly scope)
            service = build('drive', 'v3', credentials=credentials)
            about = service.about().get(fields='user(emailAddress)').execute()
            return about.get('user', {}).get('emailAddress')
        except Exception as e:
            logger.warning("Failed to get user email: %s", e)
            return None


# Singleton instance
google_auth_service = GoogleAuthService()
