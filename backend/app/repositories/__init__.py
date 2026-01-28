"""
Repository Layer - Data access abstraction for NoobBook.

Educational Note: The repository pattern provides a clean abstraction between
business logic and data storage. This enables:
- Easy switching between storage backends (JSON -> Supabase)
- Better testability (mock repositories in tests)
- Separation of concerns (services don't know about storage details)

Usage:
    from app.repositories import get_project_repository

    repo = get_project_repository()
    projects = repo.list_all()
    project = repo.get_by_id("uuid")

Architecture:
    repositories/
    ├── __init__.py         # Factory functions (this file)
    ├── base.py             # Abstract base class
    ├── projects/           # Project repository
    ├── chats/              # Chat repository
    ├── messages/           # Message repository
    ├── sources/            # Source repository
    ├── tasks/              # Task repository
    ├── studio/             # Studio job repository
    └── chunks/             # Chunk repository (for RAG)
"""
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.projects.interface import ProjectRepositoryInterface
    from app.repositories.chats.interface import ChatRepositoryInterface
    from app.repositories.messages.interface import MessageRepositoryInterface
    from app.repositories.sources.interface import SourceRepositoryInterface
    from app.repositories.tasks.interface import TaskRepositoryInterface
    from app.repositories.studio.interface import StudioRepositoryInterface
    from app.repositories.chunks.interface import ChunkRepositoryInterface


# =============================================================================
# Storage Backend Configuration
# =============================================================================

def _use_supabase() -> bool:
    """
    Check if Supabase should be used for storage.

    Educational Note: We check if Supabase is configured and available.
    If not, we fall back to JSON file storage for development.
    """
    # Check environment variable
    use_supabase = os.getenv("USE_SUPABASE", "false").lower() == "true"

    if not use_supabase:
        return False

    # Check if Supabase is actually configured
    try:
        from app.config.supabase import get_supabase_client
        client = get_supabase_client()
        return client is not None
    except Exception:
        return False


# =============================================================================
# Repository Factory Functions
# =============================================================================

_project_repo = None
_chat_repo = None
_message_repo = None
_source_repo = None
_task_repo = None
_studio_repo = None
_chunk_repo = None


def get_project_repository() -> "ProjectRepositoryInterface":
    """
    Get the project repository singleton.

    Returns Supabase or JSON implementation based on configuration.
    """
    global _project_repo

    if _project_repo is not None:
        return _project_repo

    if _use_supabase():
        from app.repositories.projects.supabase_repository import SupabaseProjectRepository
        _project_repo = SupabaseProjectRepository()
    else:
        from app.repositories.projects.json_repository import JsonProjectRepository
        _project_repo = JsonProjectRepository()

    return _project_repo


def get_chat_repository() -> "ChatRepositoryInterface":
    """Get the chat repository singleton."""
    global _chat_repo

    if _chat_repo is not None:
        return _chat_repo

    if _use_supabase():
        from app.repositories.chats.supabase_repository import SupabaseChatRepository
        _chat_repo = SupabaseChatRepository()
    else:
        from app.repositories.chats.json_repository import JsonChatRepository
        _chat_repo = JsonChatRepository()

    return _chat_repo


def get_message_repository() -> "MessageRepositoryInterface":
    """Get the message repository singleton."""
    global _message_repo

    if _message_repo is not None:
        return _message_repo

    if _use_supabase():
        from app.repositories.messages.supabase_repository import SupabaseMessageRepository
        _message_repo = SupabaseMessageRepository()
    else:
        from app.repositories.messages.json_repository import JsonMessageRepository
        _message_repo = JsonMessageRepository()

    return _message_repo


def get_source_repository() -> "SourceRepositoryInterface":
    """Get the source repository singleton."""
    global _source_repo

    if _source_repo is not None:
        return _source_repo

    if _use_supabase():
        from app.repositories.sources.supabase_repository import SupabaseSourceRepository
        _source_repo = SupabaseSourceRepository()
    else:
        from app.repositories.sources.json_repository import JsonSourceRepository
        _source_repo = JsonSourceRepository()

    return _source_repo


def get_task_repository() -> "TaskRepositoryInterface":
    """Get the task repository singleton."""
    global _task_repo

    if _task_repo is not None:
        return _task_repo

    if _use_supabase():
        from app.repositories.tasks.supabase_repository import SupabaseTaskRepository
        _task_repo = SupabaseTaskRepository()
    else:
        from app.repositories.tasks.json_repository import JsonTaskRepository
        _task_repo = JsonTaskRepository()

    return _task_repo


def get_studio_repository() -> "StudioRepositoryInterface":
    """Get the studio job repository singleton."""
    global _studio_repo

    if _studio_repo is not None:
        return _studio_repo

    if _use_supabase():
        from app.repositories.studio.supabase_repository import SupabaseStudioRepository
        _studio_repo = SupabaseStudioRepository()
    else:
        from app.repositories.studio.json_repository import JsonStudioRepository
        _studio_repo = JsonStudioRepository()

    return _studio_repo


def get_chunk_repository() -> "ChunkRepositoryInterface":
    """Get the chunk repository singleton."""
    global _chunk_repo

    if _chunk_repo is not None:
        return _chunk_repo

    if _use_supabase():
        from app.repositories.chunks.supabase_repository import SupabaseChunkRepository
        _chunk_repo = SupabaseChunkRepository()
    else:
        from app.repositories.chunks.json_repository import JsonChunkRepository
        _chunk_repo = JsonChunkRepository()

    return _chunk_repo


def reset_repositories():
    """
    Reset all repository singletons.

    Educational Note: This is mainly used in tests to ensure fresh
    repositories after changing configuration.
    """
    global _project_repo, _chat_repo, _message_repo, _source_repo
    global _task_repo, _studio_repo, _chunk_repo

    _project_repo = None
    _chat_repo = None
    _message_repo = None
    _source_repo = None
    _task_repo = None
    _studio_repo = None
    _chunk_repo = None
