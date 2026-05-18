"""
Supabase Client - Centralized Supabase client initialization.

Educational Note: This module provides a singleton Supabase client instance
that can be imported throughout the application. It handles configuration
from environment variables and provides a clean interface for database operations.
"""

import logging
import os
import threading
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
            logger.info("Supabase client initialized (%s key): %s", key_type, supabase_url)
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


def create_dedicated_client() -> Client:
    """Create a fresh, non-shared Supabase Client.

    Why: supabase-py stores the auth session ON the client object. Calling
    `client.auth.sign_in_with_password(...)` flips that client's identity
    to the just-signed-in user's JWT, and every subsequent `.table()` /
    `.rpc()` call from THAT client now sends the user's JWT instead of
    the service key. If `auth_service` shared the data singleton (it did
    until 2026-05-16), a single sign-in would silently downgrade the
    backend's role from `service_role` to `authenticated` — producing
    permission errors on RLS-gated tables and RPCs that only service_role
    is allowed to hit (e.g. `exec_freshdesk_query` after PR #266's
    REVOKE).

    Auth flows hold their own dedicated instance so this pollution stays
    contained. Data calls keep using `get_supabase()` and the singleton's
    identity stays as service_role.

    Returns a NEW client every call; caller is expected to hold the
    reference.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY (or ANON_KEY) must be set")
    return create_client(supabase_url, supabase_key)


# Process-wide dedicated clients for the two roles that must not share state
# with the data singleton. Lazy-initialised; locked so the first concurrent
# requests don't race and build two clients.
_auth_verifier_client: Optional[Client] = None
_auth_verifier_lock = threading.Lock()

_service_role_client: Optional[Client] = None
_service_role_lock = threading.Lock()


def get_auth_verifier_client() -> Client:
    """Dedicated client used ONLY for verifying user JWTs.

    Why: supabase-py 2.x registers an `on_auth_state_change` listener on
    the Client that resets `self._postgrest` and rewrites
    `self.options.headers['Authorization']` whenever the gotrue client
    fires SIGNED_IN / TOKEN_REFRESHED. Calling `auth.get_user(token)`
    against the data singleton from `get_supabase()` can — depending on
    gotrue's in-memory session state and the events it emits — flip the
    singleton's role from `service_role` to `authenticated`. Once
    flipped, every subsequent `.table()` / `.rpc()` from the singleton
    runs as the user, which 42501-s any RPC the migrations revoked from
    authenticated (notably `exec_freshdesk_query` after migration 00037).

    Symptoms we have seen in production: a sign-in is followed within
    seconds by `permission denied for function exec_freshdesk_query`
    that only clears on container restart.

    Use this client EXCLUSIVELY for `auth.get_user(token)` /
    revocation-check calls. Never call `.table()` / `.rpc()` on it —
    pollution stays contained even if the listener fires.
    """
    global _auth_verifier_client
    if _auth_verifier_client is None:
        with _auth_verifier_lock:
            if _auth_verifier_client is None:
                _auth_verifier_client = create_dedicated_client()
    return _auth_verifier_client


def get_service_role_client() -> Client:
    """Dedicated service-role client for calls that must run as service_role.

    Defense-in-depth twin of `get_auth_verifier_client`. Even though the
    auth verifier already keeps gotrue events off the data singleton,
    some future code path could regress that. RPCs that the migrations
    revoked from `authenticated` (e.g. `exec_freshdesk_query`) need a
    hard guarantee that their client's Authorization header stays
    `Bearer <SUPABASE_SERVICE_KEY>` for the life of the process.

    Use this client for RPCs that are revoked from `authenticated`.
    Never call `auth.*` methods on it — that is what guarantees the
    listener never fires and the postgrest header never flips.

    Hard-requires `SUPABASE_SERVICE_KEY`: falling back to the anon key
    would silently produce a non-service-role client and only surface
    as a 42501 inside the RPC — defeating the entire point of having
    a separately-named accessor for this. Mirrors the explicit check
    in `user_service.__init__`.
    """
    global _service_role_client
    if _service_role_client is None:
        with _service_role_lock:
            if _service_role_client is None:
                supabase_url = os.getenv("SUPABASE_URL")
                service_key = os.getenv("SUPABASE_SERVICE_KEY")
                if not supabase_url or not service_key:
                    raise RuntimeError(
                        "get_service_role_client() requires SUPABASE_URL and "
                        "SUPABASE_SERVICE_KEY. Anon key is not accepted here — "
                        "callers (e.g. exec_freshdesk_query) need a hard "
                        "service_role guarantee, and the anon fallback would "
                        "silently 42501 at call time. Set SUPABASE_SERVICE_KEY "
                        "in the backend env."
                    )
                _service_role_client = create_client(supabase_url, service_key)
    return _service_role_client


def is_supabase_enabled() -> bool:
    """
    Check if Supabase integration is enabled.

    Returns:
        True if Supabase is configured, False otherwise

    Educational Note: This allows the application to gracefully handle
    cases where Supabase is not yet configured during initial setup.
    """
    return SupabaseClient.is_configured()
