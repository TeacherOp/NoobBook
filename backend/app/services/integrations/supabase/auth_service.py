"""
Supabase Auth Service - User authentication and session management.

Educational Note: This service handles all authentication operations using
Supabase Auth. It provides a clean interface for sign up, sign in, sign out,
and session management.
"""

from typing import Dict, Any, Optional
from supabase import Client
from .supabase_client import get_supabase


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
                self._create_user_profile(response.user.id, email)

            return {"success": True, "user": response.user, "session": response.session}
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

            return {"success": True, "user": response.user, "session": response.session}
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

    def _create_user_profile(self, user_id: str, email: str) -> None:
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
            self.supabase.table("users").insert(
                {"id": user_id, "email": email, "memory": {}, "settings": {}}
            ).execute()
        except Exception as e:
            print(f"Warning: Failed to create user profile: {e}")


# Singleton instance
auth_service = AuthService()
