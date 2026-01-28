"""
Storage Service - Abstraction layer for file storage operations.

Educational Note: This module provides a unified interface for file storage,
allowing transparent switching between local filesystem and Supabase Storage.
This enables gradual migration without changing calling code.

Usage:
    from app.services.storage import get_storage_service

    storage = get_storage_service()

    # Upload a file
    path = storage.upload_file(project_id, "raw", file_data, filename)

    # Download a file
    data = storage.download_file(project_id, "raw", filename)

    # Delete a file
    storage.delete_file(project_id, "raw", filename)

Storage Categories:
    - raw: Original uploaded files (PDFs, images, audio, etc.)
    - processed: Extracted text files (.txt)
    - chunks: Chunked text for RAG (per-source directories)
    - studio/audio: Generated audio files
    - studio/scripts: Generated script files
    - ai_outputs: AI-generated content (plots, images)
"""
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.storage.interface import StorageServiceInterface


def _use_supabase_storage() -> bool:
    """Check if Supabase Storage should be used."""
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "false").lower() == "true"

    if not use_supabase:
        return False

    try:
        from app.config.supabase import get_supabase_storage
        storage = get_supabase_storage()
        return storage is not None
    except Exception:
        return False


_storage_service = None


def get_storage_service() -> "StorageServiceInterface":
    """
    Get the storage service singleton.

    Returns Supabase or Local implementation based on configuration.
    """
    global _storage_service

    if _storage_service is not None:
        return _storage_service

    if _use_supabase_storage():
        from app.services.storage.supabase_storage import SupabaseStorageService
        _storage_service = SupabaseStorageService()
    else:
        from app.services.storage.local_storage import LocalStorageService
        _storage_service = LocalStorageService()

    return _storage_service


def reset_storage_service():
    """Reset the storage service singleton (for testing)."""
    global _storage_service
    _storage_service = None


__all__ = ['get_storage_service', 'reset_storage_service']
