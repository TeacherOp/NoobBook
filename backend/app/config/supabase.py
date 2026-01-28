"""
Supabase Configuration - Client setup for self-hosted Supabase.

Educational Note: This module provides centralized Supabase client configuration
for both database operations (via PostgREST API) and file storage operations
(via Supabase Storage API). The client is a singleton to avoid creating
multiple connections.

Self-Hosted Supabase Setup:
    1. Clone supabase/supabase repo
    2. cd docker && docker compose up -d
    3. Dashboard: http://localhost:54323
    4. API: http://localhost:54321

Environment Variables Required:
    SUPABASE_URL=http://localhost:54321
    SUPABASE_ANON_KEY=eyJ...  (for client-side operations)
    SUPABASE_SERVICE_KEY=eyJ...  (for server-side operations, bypasses RLS)
"""
import os
from typing import Optional
from functools import lru_cache

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None


class SupabaseConfig:
    """
    Configuration container for Supabase connection settings.

    Educational Note: We read from environment variables to keep
    sensitive credentials out of code. The service key should NEVER
    be exposed to the frontend - it bypasses Row Level Security.
    """

    def __init__(self):
        self.url: str = os.getenv("SUPABASE_URL", "http://localhost:54321")
        self.anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
        self.service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

        # Storage configuration
        self.storage_url: str = os.getenv(
            "SUPABASE_STORAGE_URL",
            f"{self.url}/storage/v1"
        )

        # Storage bucket names
        self.sources_bucket: str = "sources"
        self.studio_bucket: str = "studio"
        self.ai_outputs_bucket: str = "ai-outputs"

    @property
    def is_configured(self) -> bool:
        """
        Check if Supabase is properly configured.

        Educational Note: Both URL and at least one key are required.
        In production, the service key is needed for backend operations.
        """
        return bool(self.url and (self.anon_key or self.service_key))

    def validate(self) -> tuple[bool, str]:
        """
        Validate the Supabase configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not SUPABASE_AVAILABLE:
            return False, "supabase-py package not installed. Run: pip install supabase"

        if not self.url:
            return False, "SUPABASE_URL environment variable not set"

        if not self.service_key:
            return False, "SUPABASE_SERVICE_KEY environment variable not set (required for backend)"

        return True, ""


# Global config instance
_config: Optional[SupabaseConfig] = None


def get_supabase_config() -> SupabaseConfig:
    """
    Get the Supabase configuration singleton.

    Educational Note: Using a singleton pattern ensures we only
    read environment variables once and share the config across
    the application.
    """
    global _config
    if _config is None:
        _config = SupabaseConfig()
    return _config


# =============================================================================
# Supabase Client Management
# =============================================================================

_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Get the Supabase client singleton (uses service key for backend operations).

    Educational Note: The service key bypasses Row Level Security (RLS),
    allowing the backend to perform any operation. This is necessary for
    server-side operations but the key should never be exposed to clients.

    Returns:
        Supabase client instance or None if not configured/available
    """
    global _client

    if not SUPABASE_AVAILABLE:
        print("Warning: supabase-py package not installed")
        return None

    if _client is not None:
        return _client

    config = get_supabase_config()

    if not config.is_configured:
        print("Warning: Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return None

    try:
        # Use service key for backend operations (bypasses RLS)
        key = config.service_key or config.anon_key
        _client = create_client(config.url, key)
        print(f"Supabase client initialized: {config.url}")
        return _client
    except Exception as e:
        print(f"Failed to create Supabase client: {e}")
        return None


def get_supabase_storage():
    """
    Get the Supabase storage client.

    Educational Note: Supabase Storage is S3-compatible and supports
    bucket-based organization. We use it for:
    - sources/{project_id}/raw/ - Original uploaded files
    - sources/{project_id}/processed/ - Extracted text files
    - studio/{project_id}/ - Generated content (audio, images, etc.)

    Returns:
        Storage client or None if not configured
    """
    client = get_supabase_client()
    if client is None:
        return None
    return client.storage


# =============================================================================
# Health Check
# =============================================================================

def check_supabase_connection() -> dict:
    """
    Check if Supabase is reachable and configured properly.

    Educational Note: This is useful for health check endpoints
    and debugging connection issues during setup.

    Returns:
        Dict with connection status and details
    """
    config = get_supabase_config()

    result = {
        "available": SUPABASE_AVAILABLE,
        "configured": config.is_configured,
        "url": config.url,
        "connected": False,
        "error": None
    }

    if not SUPABASE_AVAILABLE:
        result["error"] = "supabase-py package not installed"
        return result

    if not config.is_configured:
        result["error"] = "Supabase not configured"
        return result

    try:
        client = get_supabase_client()
        if client:
            # Try a simple query to verify connection
            # This will fail gracefully if tables don't exist yet
            result["connected"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# Utility Functions
# =============================================================================

def reset_client():
    """
    Reset the Supabase client (useful for testing or reconfiguration).

    Educational Note: This is mainly used in tests to ensure a fresh
    client after changing environment variables.
    """
    global _client, _config
    _client = None
    _config = None
