"""
Supabase Client - Centralized Supabase client initialization.

Educational Note: This module provides a singleton Supabase client instance
that can be imported throughout the application. It handles configuration
from environment variables and provides a clean interface for database operations.
"""

import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SupabaseClient:
    """
    Singleton Supabase client wrapper.

    Educational Note: Using a singleton pattern ensures we only create one
    Supabase client instance throughout the application lifecycle, which is
    more efficient and prevents connection issues.
    """

    _instance: Optional[Client] = None
    _initialized: bool = False

    @classmethod
    def get_client(cls) -> Client:
        """
        Get or create the Supabase client instance.

        Returns:
            Supabase client instance

        Raises:
            ValueError: If required environment variables are not set
        """
        if not cls._initialized:
            cls._initialize()

        if cls._instance is None:
            raise RuntimeError("Supabase client failed to initialize")

        return cls._instance

    @classmethod
    def _initialize(cls) -> None:
        """
        Initialize the Supabase client from environment variables.

        Educational Note: We use the SERVICE_KEY (not anon key) for single-user mode
        because it bypasses Row Level Security (RLS). This is safe for local/single-user
        deployments. For multi-user production, use anon key with proper auth.
        """
        supabase_url = os.getenv("SUPABASE_URL")
        # Prefer service key for single-user mode (bypasses RLS)
        # Fall back to anon key for backwards compatibility
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url:
            raise ValueError(
                "SUPABASE_URL environment variable is not set. "
                "Please add it to your .env file."
            )

        if not supabase_key:
            raise ValueError(
                "SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY environment variable is not set. "
                "Please add SUPABASE_SERVICE_KEY to your .env file for single-user mode."
            )

        try:
            cls._instance = create_client(supabase_url, supabase_key)
            cls._initialized = True
            key_type = "service" if os.getenv("SUPABASE_SERVICE_KEY") else "anon"
            print(f"✓ Supabase client initialized ({key_type} key): {supabase_url}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Supabase client: {str(e)}")

    @classmethod
    def is_configured(cls) -> bool:
        """
        Check if Supabase is configured (environment variables are set).

        Returns:
            True if configured, False otherwise
        """
        has_url = bool(os.getenv("SUPABASE_URL"))
        has_key = bool(os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"))
        return has_url and has_key

    @classmethod
    def reset(cls) -> None:
        """
        Reset the client instance (useful for testing).

        Educational Note: This method allows tests to reset the singleton
        state between test runs.
        """
        cls._instance = None
        cls._initialized = False


# Convenience function for easy importing
def get_supabase() -> Client:
    """
    Get the Supabase client instance.

    This is the recommended way to access the Supabase client throughout
    the application.

    Returns:
        Supabase client instance

    Example:
        from app.services.integrations.supabase import get_supabase

        supabase = get_supabase()
        projects = supabase.table("projects").select("*").execute()
    """
    return SupabaseClient.get_client()


def is_supabase_enabled() -> bool:
    """
    Check if Supabase integration is enabled.

    Returns:
        True if Supabase is configured, False otherwise

    Educational Note: This allows the application to gracefully handle
    cases where Supabase is not configured (e.g., during development
    with JSON files only).
    """
    return SupabaseClient.is_configured()
