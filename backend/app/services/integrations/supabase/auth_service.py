"""
Supabase Auth Service - User authentication and session management.

Educational Note: This service handles all authentication operations using
Supabase Auth. It provides a clean interface for sign up, sign in, sign out,
and session management.
"""

import logging
from typing import Dict, Any, Optional, Iterable
import os
from supabase import Client
from .supabase_client import get_supabase

logger = logging.getLogger(__name__)


class AuthService:
    """
    Service for user authentication operations.

    Educational Note: This service wraps Supabase Auth methods to provide
    a consistent interface and handle errors gracefully.
    """

    def __init__(self):
        """Initialize the auth service with Supabase client."""
        self.supabase: Client = get_supabase()

    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user with email and password.

        Args:
            email: User's email address
            password: User's password (min 6 characters recommended)

        Returns:
            Dict containing user data and session

        Raises:
            Exception: If sign up fails (e.g., email already exists)

        Educational Note: Supabase handles password hashing, email validation,
        and user creation automatically. The user is created in the auth.users
        table, and we can add additional data to our public.users table.
        """
        try:
            response = self.supabase.auth.sign_up(
                {"email": email, "password": password}
            )

            # Create corresponding user record in public.users table
            if response.user:
                role = self._resolve_signup_role(email)
                self._create_user_profile(response.user.id, email, role=role)

            return {
                "success": True,
                "user": self._serialize_user(response.user),
                "session": self._serialize_session(response.session),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in an existing user with email and password.

        Args:
            email: User's email address
            password: User's password

        Returns:
            Dict containing user data and session

        Raises:
            Exception: If sign in fails (invalid credentials)

        Educational Note: Supabase returns a JWT token in the session object.
        This token should be stored client-side and included in subsequent
        requests for authentication.
        """
        try:
            response = self.supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )

            return {
                "success": True,
                "user": self._serialize_user(response.user),
                "session": self._serialize_session(response.session),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sign_out(self) -> Dict[str, Any]:
        """
        Sign out the current user.

        Returns:
            Dict indicating success or failure

        Educational Note: This invalidates the current session token.
        The client should clear the stored token after calling this.
        """
        try:
            self.supabase.auth.sign_out()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently authenticated user.

        Returns:
            User data if authenticated, None otherwise

        Educational Note: This uses the JWT token from the current session
        to retrieve user information. The token must be valid and not expired.
        """
        try:
            response = self.supabase.auth.get_user()
            return response.user if response else None
        except Exception:
            return None

    def get_session(self) -> Optional[Dict[str, Any]]:
        """
        Get the current session.

        Returns:
            Session data if authenticated, None otherwise
        """
        try:
            response = self.supabase.auth.get_session()
            return response if response else None
        except Exception:
            return None

    def refresh_session(self) -> Dict[str, Any]:
        """
        Refresh the current session token.

        Returns:
            Dict containing new session data

        Educational Note: JWT tokens expire after a certain time (default 1 hour).
        This method gets a new token using the refresh token, extending the session.
        """
        try:
            response = self.supabase.auth.refresh_session()
            return {"success": True, "session": response.session}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refresh_with_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh session using a client-provided refresh token.

        Educational Note: Unlike refresh_session() which uses the server-side session,
        this method accepts a refresh token from the client. This is needed because
        the frontend stores its own tokens and the server doesn't maintain session state.
        When the access_token (JWT) expires, the client sends its refresh_token here
        to get a new token pair without requiring the user to re-login.
        """
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            return {
                "success": True,
                "session": self._serialize_session(response.session),
            }
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            return {"success": False, "error": "Token refresh failed"}

    def reset_password_email(self, email: str) -> Dict[str, Any]:
        """
        Send a password reset email to the user.

        Args:
            email: User's email address

        Returns:
            Dict indicating success or failure

        Educational Note: Supabase sends an email with a secure link to reset
        the password. The link expires after a certain time for security.
        """
        try:
            self.supabase.auth.reset_password_for_email(email)
            return {"success": True, "message": "Password reset email sent"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_user(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the current user's data.

        Args:
            updates: Dict of fields to update (e.g., {"email": "new@email.com"})

        Returns:
            Dict containing updated user data

        Educational Note: This can update email, password, or user metadata.
        Email changes require confirmation if email confirmation is enabled.
        """
        try:
            response = self.supabase.auth.update_user(updates)
            return {"success": True, "user": response.user}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def bootstrap_admin_from_env(self) -> bool:
        """
        Ensure a bootstrap admin exists when env vars are provided.

        Env vars:
        - NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL
        - NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD
        - NOOBBOOK_BOOTSTRAP_ADMIN_FORCE_RESET (optional)
        """
        email = (os.getenv("NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL") or "").strip()
        password = (os.getenv("NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
        force_reset = (os.getenv("NOOBBOOK_BOOTSTRAP_ADMIN_FORCE_RESET") or "").strip().lower()

        if not email or not password:
            return False

        force_reset_enabled = force_reset in {"1", "true", "yes", "on"}
        normalized_email = self._normalize_email(email)

        try:
            existing_user = self._find_user_by_email(normalized_email)
            if existing_user:
                if force_reset_enabled:
                    self.supabase.auth.admin.update_user_by_id(existing_user.id, {"password": password})
                self._ensure_user_profile(existing_user.id, normalized_email, role="admin")
                return True

            response = self.supabase.auth.admin.create_user(
                {"email": normalized_email, "password": password, "email_confirm": True}
            )
            created_user = getattr(response, "user", None) or response
            if created_user:
                self._ensure_user_profile(created_user.id, normalized_email, role="admin")
                return True
        except Exception as e:
            logger.warning("Failed to bootstrap admin user: %s", e)

        return False

    def _create_user_profile(self, user_id: str, email: str, role: str = "user") -> None:
        """
        Create a user profile in the public.users table.

        Args:
            user_id: The auth user's UUID
            email: User's email address

        Educational Note: Supabase Auth creates users in the auth.users table.
        We create a corresponding record in public.users to store additional
        user data like memory and settings.
        """
        try:
            # Lazy import to avoid the user_service's own import-time Supabase
            # init when this auth path runs in environments where user_service
            # hasn't been needed yet.
            from app.services.data_services.user_service import default_user_settings

            self.supabase.table("users").insert(
                {
                    "id": user_id,
                    "email": email,
                    "role": role,
                    "memory": {},
                    "settings": default_user_settings(),
                }
            ).execute()
        except Exception as e:
            logger.warning("Failed to create user profile: %s", e)

    def _ensure_user_profile(self, user_id: str, email: str, role: str = "user") -> None:
        """
        Ensure the public.users profile exists and has the correct role.
        """
        try:
            resp = self.supabase.table("users").select("id").eq("id", user_id).execute()
            if resp.data:
                self.supabase.table("users").update({"email": email, "role": role}).eq("id", user_id).execute()
            else:
                self._create_user_profile(user_id, email, role=role)
        except Exception as e:
            logger.warning("Failed to ensure user profile: %s", e)

    def _find_user_by_email(self, email: str):
        try:
            response = self.supabase.auth.admin.list_users()
            users: Iterable = getattr(response, "users", None) or response
            for user in users or []:
                if self._normalize_email(getattr(user, "email", None) or "") == email:
                    return user
        except Exception:
            return None
        return None

    @staticmethod
    def _normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    def _resolve_signup_role(self, email: str) -> str:
        """
        Determine role for a newly signed-up user.

        Rules:
        1) If email is in NOOBBOOK_ADMIN_EMAILS -> admin
        2) If email matches NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL -> admin
           (persisted permanently in docker/.env by setup.sh; behaves
           like an implicit entry in NOOBBOOK_ADMIN_EMAILS for all
           future signups with that address, not only the first deploy)
        3) Else -> user

        The previous "if no admins exist, auto-promote the first signup
        to admin" branch was removed. That branch let whoever found the
        deploy URL first claim admin without any operator intent —
        operators now bootstrap explicitly via the env var path
        (`bootstrap_admin_from_env()` or NOOBBOOK_ADMIN_EMAILS).
        """
        normalized = email.strip().lower()

        admin_emails = os.getenv("NOOBBOOK_ADMIN_EMAILS", "")
        admin_list = [e.strip().lower() for e in admin_emails.split(",") if e.strip()]
        if normalized in admin_list:
            return "admin"

        bootstrap_email = (os.getenv("NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
        if bootstrap_email and normalized == bootstrap_email:
            return "admin"

        return "user"

    @staticmethod
    def _serialize_user(user: Any) -> Optional[Dict[str, Any]]:
        if not user:
            return None
        # supabase-py returns User object or dict
        if isinstance(user, dict):
            return {"id": user.get("id"), "email": user.get("email")}
        return {"id": getattr(user, "id", None), "email": getattr(user, "email", None)}

    @staticmethod
    def _serialize_session(session: Any) -> Optional[Dict[str, Any]]:
        if not session:
            return None
        if isinstance(session, dict):
            return {
                "access_token": session.get("access_token"),
                "refresh_token": session.get("refresh_token"),
                "expires_in": session.get("expires_in"),
                "token_type": session.get("token_type"),
            }
        return {
            "access_token": getattr(session, "access_token", None),
            "refresh_token": getattr(session, "refresh_token", None),
            "expires_in": getattr(session, "expires_in", None),
            "token_type": getattr(session, "token_type", None),
        }


# Singleton instance
auth_service = AuthService()
