#!/usr/bin/env python3
"""
NoobBook Data Migration Script - JSON to Supabase

Educational Note: This script migrates all existing JSON file data to Supabase
PostgreSQL. It handles:
- Projects and their settings/cost tracking
- Sources and their metadata
- Chats and messages
- Chunks for RAG
- Studio jobs
- User/project memory

Usage:
    # Preview what will be migrated
    python scripts/migrate_to_supabase.py --dry-run

    # Run migration
    python scripts/migrate_to_supabase.py

    # Migrate specific entities
    python scripts/migrate_to_supabase.py --only projects,sources
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


# Default user ID for single-user mode
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


class MigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.projects = 0
        self.sources = 0
        self.chats = 0
        self.messages = 0
        self.chunks = 0
        self.studio_jobs = 0
        self.errors: List[str] = []

    def summary(self) -> str:
        return f"""
Migration Summary:
  Projects: {self.projects}
  Sources: {self.sources}
  Chats: {self.chats}
  Messages: {self.messages}
  Chunks: {self.chunks}
  Studio Jobs: {self.studio_jobs}
  Errors: {len(self.errors)}
"""


class NoobBookMigration:
    """Handles migration from JSON to Supabase."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = MigrationStats()
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from app.config.supabase import get_supabase_client
            self._client = get_supabase_client()
            if self._client is None:
                raise RuntimeError(
                    "Supabase client not available. "
                    "Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set."
                )
        return self._client

    def _log(self, message: str):
        """Log a message."""
        prefix = "[DRY RUN] " if self.dry_run else ""
        print(f"{prefix}{message}")

    def _error(self, message: str):
        """Log an error."""
        self.stats.errors.append(message)
        print(f"ERROR: {message}")

    # =========================================================================
    # Load JSON Data
    # =========================================================================

    def _load_projects_index(self) -> List[Dict[str, Any]]:
        """Load projects index."""
        index_path = Config.PROJECTS_DIR / "projects_index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, 'r') as f:
                data = json.load(f)
                return data.get("projects", [])
        except Exception as e:
            self._error(f"Failed to load projects index: {e}")
            return []

    def _load_project_file(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Load a project's JSON file."""
        project_file = Config.PROJECTS_DIR / f"{project_id}.json"
        if not project_file.exists():
            return None
        try:
            with open(project_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self._error(f"Failed to load project {project_id}: {e}")
            return None

    def _load_sources_index(self, project_id: str) -> List[Dict[str, Any]]:
        """Load sources index for a project."""
        index_path = Config.PROJECTS_DIR / project_id / "sources" / "sources_index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, 'r') as f:
                data = json.load(f)
                return data.get("sources", [])
        except Exception as e:
            self._error(f"Failed to load sources for {project_id}: {e}")
            return []

    def _load_chats_index(self, project_id: str) -> List[Dict[str, Any]]:
        """Load chats index for a project."""
        index_path = Config.PROJECTS_DIR / project_id / "chats" / "chats_index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, 'r') as f:
                data = json.load(f)
                return data.get("chats", [])
        except Exception as e:
            self._error(f"Failed to load chats for {project_id}: {e}")
            return []

    def _load_chat_file(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Load a chat's JSON file."""
        chat_file = Config.PROJECTS_DIR / project_id / "chats" / f"{chat_id}.json"
        if not chat_file.exists():
            return None
        try:
            with open(chat_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self._error(f"Failed to load chat {chat_id}: {e}")
            return None

    def _load_studio_index(self, project_id: str) -> Dict[str, Any]:
        """Load studio index for a project."""
        index_path = Config.PROJECTS_DIR / project_id / "studio" / "studio_index.json"
        if not index_path.exists():
            return {}
        try:
            with open(index_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self._error(f"Failed to load studio for {project_id}: {e}")
            return {}

    def _load_project_memory(self, project_id: str) -> Optional[str]:
        """Load project-specific memory."""
        memory_file = Config.PROJECTS_DIR / project_id / "memory.json"
        if not memory_file.exists():
            return None
        try:
            with open(memory_file, 'r') as f:
                data = json.load(f)
                return data.get("memory")
        except Exception:
            return None

    def _load_user_memory(self) -> Optional[str]:
        """Load global user memory."""
        memory_file = Config.DATA_DIR / "user_memory.json"
        if not memory_file.exists():
            return None
        try:
            with open(memory_file, 'r') as f:
                data = json.load(f)
                return data.get("memory")
        except Exception:
            return None

    def _load_chunks(self, project_id: str, source_id: str) -> List[Dict[str, Any]]:
        """Load chunks for a source."""
        chunks_dir = Config.PROJECTS_DIR / project_id / "sources" / "chunks" / source_id
        if not chunks_dir.exists():
            return []

        chunks = []
        for chunk_file in chunks_dir.glob("*.txt"):
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse header and text
                if '# ---' not in content:
                    continue

                header, text = content.split('# ---', 1)
                text = text.strip()

                # Parse metadata from header
                metadata = {}
                for line in header.strip().split('\n'):
                    if line.startswith('# ') and ':' in line:
                        key, value = line[2:].split(':', 1)
                        metadata[key.strip()] = value.strip()

                chunks.append({
                    "id": metadata.get("chunk_id", chunk_file.stem),
                    "source_id": source_id,
                    "project_id": project_id,
                    "text": text,
                    "page_number": int(metadata.get("page", 0)),
                    "chunk_number": int(metadata.get("chunk", 0)),
                    "token_count": int(metadata.get("token_count", 0)) if metadata.get("token_count") else None
                })
            except Exception as e:
                self._error(f"Failed to parse chunk {chunk_file}: {e}")

        return chunks

    # =========================================================================
    # Migration Methods
    # =========================================================================

    def migrate_user(self):
        """Create/update default user with global memory."""
        self._log("Migrating user memory...")

        user_memory = self._load_user_memory()

        if self.dry_run:
            self._log(f"  Would create default user with memory: {bool(user_memory)}")
            return

        try:
            # Upsert default user
            self.client.table("users").upsert({
                "id": DEFAULT_USER_ID,
                "email": "default@noobbook.local",
                "display_name": "Default User",
                "user_memory": user_memory
            }).execute()
            self._log("  Default user created/updated")
        except Exception as e:
            self._error(f"Failed to migrate user: {e}")

    def migrate_projects(self):
        """Migrate all projects."""
        self._log("Migrating projects...")

        projects_index = self._load_projects_index()
        self._log(f"  Found {len(projects_index)} projects")

        for project_meta in projects_index:
            project_id = project_meta["id"]
            project_data = self._load_project_file(project_id)

            if not project_data:
                self._error(f"  Project file missing: {project_id}")
                continue

            project_memory = self._load_project_memory(project_id)

            if self.dry_run:
                self._log(f"  Would migrate project: {project_data.get('name')}")
                self.stats.projects += 1
                continue

            try:
                self.client.table("projects").upsert({
                    "id": project_id,
                    "user_id": DEFAULT_USER_ID,
                    "name": project_data.get("name"),
                    "description": project_data.get("description", ""),
                    "settings": project_data.get("settings", {}),
                    "cost_tracking": project_data.get("cost_tracking", {}),
                    "project_memory": project_memory,
                    "created_at": project_data.get("created_at"),
                    "updated_at": project_data.get("updated_at"),
                    "last_accessed": project_data.get("last_accessed", project_data.get("updated_at"))
                }).execute()

                self.stats.projects += 1
                self._log(f"  Migrated project: {project_data.get('name')}")
            except Exception as e:
                self._error(f"  Failed to migrate project {project_id}: {e}")

    def migrate_sources(self):
        """Migrate all sources."""
        self._log("Migrating sources...")

        projects_index = self._load_projects_index()

        for project_meta in projects_index:
            project_id = project_meta["id"]
            sources = self._load_sources_index(project_id)

            if not sources:
                continue

            self._log(f"  Project {project_meta.get('name')}: {len(sources)} sources")

            for source in sources:
                if self.dry_run:
                    self.stats.sources += 1
                    continue

                try:
                    # Ensure required fields
                    source_data = {
                        "id": source["id"],
                        "project_id": project_id,
                        "name": source.get("name"),
                        "source_type": source.get("source_type", source.get("type")),
                        "status": source.get("status", "uploaded"),
                        "original_filename": source.get("original_filename"),
                        "file_size": source.get("file_size"),
                        "mime_type": source.get("mime_type"),
                        "token_count": source.get("token_count"),
                        "page_count": source.get("page_count"),
                        "embedding_info": source.get("embedding_info"),
                        "summary_info": source.get("summary_info"),
                        "metadata": source.get("metadata", {}),
                        "active": source.get("active", True),
                        "created_at": source.get("created_at"),
                        "updated_at": source.get("updated_at")
                    }

                    self.client.table("sources").upsert(source_data).execute()
                    self.stats.sources += 1
                except Exception as e:
                    self._error(f"  Failed to migrate source {source['id']}: {e}")

    def migrate_chats_and_messages(self):
        """Migrate all chats and their messages."""
        self._log("Migrating chats and messages...")

        projects_index = self._load_projects_index()

        for project_meta in projects_index:
            project_id = project_meta["id"]
            chats_index = self._load_chats_index(project_id)

            if not chats_index:
                continue

            self._log(f"  Project {project_meta.get('name')}: {len(chats_index)} chats")

            for chat_meta in chats_index:
                chat_id = chat_meta["id"]
                chat_data = self._load_chat_file(project_id, chat_id)

                if not chat_data:
                    continue

                messages = chat_data.get("messages", [])

                if self.dry_run:
                    self.stats.chats += 1
                    self.stats.messages += len(messages)
                    continue

                try:
                    # Migrate chat
                    self.client.table("chats").upsert({
                        "id": chat_id,
                        "project_id": project_id,
                        "title": chat_data.get("title", "New Chat"),
                        "message_count": len(messages),
                        "metadata": chat_data.get("metadata", {}),
                        "studio_signals": chat_data.get("studio_signals", []),
                        "created_at": chat_data.get("created_at"),
                        "updated_at": chat_data.get("updated_at")
                    }).execute()
                    self.stats.chats += 1

                    # Migrate messages
                    for seq, msg in enumerate(messages, 1):
                        self.client.table("messages").upsert({
                            "id": msg.get("id"),
                            "chat_id": chat_id,
                            "role": msg.get("role"),
                            "content": msg.get("content"),
                            "sequence_number": seq,
                            "model": msg.get("model"),
                            "tokens": msg.get("tokens"),
                            "is_error": msg.get("error", False),
                            "created_at": msg.get("timestamp")
                        }).execute()
                        self.stats.messages += 1

                except Exception as e:
                    self._error(f"  Failed to migrate chat {chat_id}: {e}")

    def migrate_chunks(self):
        """Migrate all chunks."""
        self._log("Migrating chunks...")

        projects_index = self._load_projects_index()

        for project_meta in projects_index:
            project_id = project_meta["id"]
            sources = self._load_sources_index(project_id)

            for source in sources:
                source_id = source["id"]
                chunks = self._load_chunks(project_id, source_id)

                if not chunks:
                    continue

                if self.dry_run:
                    self.stats.chunks += len(chunks)
                    continue

                self._log(f"  Source {source.get('name')}: {len(chunks)} chunks")

                try:
                    # Batch insert chunks
                    for chunk in chunks:
                        self.client.table("chunks").upsert(chunk).execute()
                        self.stats.chunks += 1
                except Exception as e:
                    self._error(f"  Failed to migrate chunks for {source_id}: {e}")

    def migrate_studio_jobs(self):
        """Migrate all studio jobs."""
        self._log("Migrating studio jobs...")

        projects_index = self._load_projects_index()

        # Job type to index key mapping
        job_types = [
            ("audio", "audio_jobs"),
            ("video", "video_jobs"),
            ("ad", "ad_jobs"),
            ("flash_cards", "flash_card_jobs"),
            ("mind_map", "mind_map_jobs"),
            ("quiz", "quiz_jobs"),
            ("social_post", "social_post_jobs"),
            ("infographic", "infographic_jobs"),
            ("email", "email_jobs"),
            ("website", "website_jobs"),
            ("component", "component_jobs"),
            ("flow_diagram", "flow_diagram_jobs"),
            ("wireframe", "wireframe_jobs"),
            ("presentation", "presentation_jobs"),
            ("prd", "prd_jobs"),
            ("marketing_strategy", "marketing_strategy_jobs"),
            ("blog", "blog_jobs"),
            ("business_report", "business_report_jobs"),
        ]

        for project_meta in projects_index:
            project_id = project_meta["id"]
            studio_index = self._load_studio_index(project_id)

            if not studio_index:
                continue

            for job_type, index_key in job_types:
                jobs = studio_index.get(index_key, [])

                for job in jobs:
                    if self.dry_run:
                        self.stats.studio_jobs += 1
                        continue

                    try:
                        self.client.table("studio_jobs").upsert({
                            "id": job.get("id"),
                            "project_id": project_id,
                            "job_type": job_type,
                            "status": job.get("status", "pending"),
                            "error_message": job.get("error_message"),
                            "config": job.get("config", {}),
                            "output": job.get("output", {}),
                            "output_paths": job.get("output_paths", {}),
                            "created_at": job.get("created_at"),
                            "updated_at": job.get("updated_at"),
                            "completed_at": job.get("completed_at")
                        }).execute()
                        self.stats.studio_jobs += 1
                    except Exception as e:
                        self._error(f"  Failed to migrate job {job.get('id')}: {e}")

    def run(self, only: Optional[List[str]] = None):
        """Run the full migration."""
        self._log("=" * 60)
        self._log("NoobBook Data Migration: JSON -> Supabase")
        self._log("=" * 60)

        if self.dry_run:
            self._log("DRY RUN MODE - No changes will be made")

        entities = only or ["user", "projects", "sources", "chats", "chunks", "studio"]

        if "user" in entities:
            self.migrate_user()

        if "projects" in entities:
            self.migrate_projects()

        if "sources" in entities:
            self.migrate_sources()

        if "chats" in entities:
            self.migrate_chats_and_messages()

        if "chunks" in entities:
            self.migrate_chunks()

        if "studio" in entities:
            self.migrate_studio_jobs()

        self._log(self.stats.summary())

        if self.stats.errors:
            self._log("Errors encountered:")
            for error in self.stats.errors:
                self._log(f"  - {error}")

        return len(self.stats.errors) == 0


def main():
    parser = argparse.ArgumentParser(description="Migrate NoobBook data to Supabase")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes"
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Comma-separated list of entities to migrate (user,projects,sources,chats,chunks,studio)"
    )

    args = parser.parse_args()

    only = args.only.split(",") if args.only else None

    migration = NoobBookMigration(dry_run=args.dry_run)
    success = migration.run(only=only)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
