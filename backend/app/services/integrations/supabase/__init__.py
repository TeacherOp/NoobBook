"""
Supabase integration module.

This module provides services for interacting with Supabase:
- supabase_client: Centralized client initialization
- auth_service: User authentication and session management
- storage_service: File storage operations (raw files, processed, chunks)
"""

from .supabase_client import (
    get_supabase,
    get_auth_verifier_client,
    get_service_role_client,
    is_supabase_enabled,
    SupabaseClient,
)
from .auth_service import auth_service, AuthService
from . import storage_service

__all__ = [
    "get_supabase",
    "get_auth_verifier_client",
    "get_service_role_client",
    "is_supabase_enabled",
    "SupabaseClient",
    "auth_service",
    "AuthService",
    "storage_service",
]
