"""
Chat Service - CRUD operations for chat entities.

Educational Note: This service manages chat entity lifecycle within projects
using Supabase as the database backend.

Separation of Concerns:
- chat_service.py: Chat CRUD (this file)
- claude_service.py: Claude API interactions
- message_service.py: Message persistence
- prompt_loader.py: Prompt management
"""
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service class for chat entity management using Supabase.

    Educational Note: A chat is a conversation container within a project.
    It has metadata (title, timestamps) and holds messages.
    """

    def __init__(self):
        """Initialize the chat service."""
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "chats"
        self.messages_table = "messages"
        self.studio_signals_table = "studio_signals"

    def list_chats(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all chats for a project.

        Educational Note: Returns metadata only (not full messages) for
        efficient loading of chat lists in the UI. A single RPC
        (`list_chats_with_message_count`, migration 00029) joins each
        chat to its filtered message count in one round-trip — the
        previous N+1 implementation made one count query per chat
        (21 round-trips for 20 chats; dominant latency on dashboard
        load with active chat history). The SQL filter mirrors
        `_is_displayable_message` so the sidebar count never drifts
        from what the chat header shows.

        A Python fallback path remains for environments where the
        migration hasn't run yet (e.g. local dev that skipped it),
        with a `logger.warning` so the issue surfaces in logs.

        Args:
            project_id: The project UUID

        Returns:
            List of chat metadata, sorted by most recent first
        """
        # Only the RPC call itself is wrapped — type coercion below
        # runs outside the try so a downstream bug doesn't get
        # swallowed as "RPC failed, falling back".
        rpc_response = None
        try:
            rpc_response = (
                self.supabase
                .rpc("list_chats_with_message_count", {"p_project_id": project_id})
                .execute()
            )
        except Exception as exc:  # noqa: BLE001 — narrowed below
            # Distinguish "migration hasn't run yet" (expected, INFO) from
            # actual operational errors (network, auth, quota — ERROR so
            # monitoring picks them up). PostgREST returns code PGRST202
            # for a missing RPC function; older Supabase stacks surface
            # the underlying Postgres "function does not exist" instead.
            msg = str(exc).lower()
            is_missing_rpc = (
                "pgrst202" in msg
                or "could not find the function" in msg
                or ("function" in msg and "does not exist" in msg)
            )
            if is_missing_rpc:
                logger.info(
                    "list_chats_with_message_count RPC not present yet; "
                    "falling back to N+1 count loop. Run migration 00029.",
                )
            else:
                logger.error(
                    "list_chats_with_message_count RPC failed (%s: %s); "
                    "falling back to N+1 count loop. Investigate — this is "
                    "NOT the missing-function case.",
                    type(exc).__name__, exc,
                )

        if rpc_response is not None:
            chats = rpc_response.data or []
            # RPC returns int8 (BIGINT). Coerce to plain int for JSON
            # symmetry with create_chat's `message_count: 0`. Non-RPC
            # errors here would NOT be miscategorized as "RPC failed".
            for chat in chats:
                chat["message_count"] = int(chat.get("message_count") or 0)
            return chats

        # Fallback: original N+1 path. Identical filter to the SQL.
        response = (
            self.supabase.table(self.table)
            .select("id, title, created_at, updated_at, costs")
            .eq("project_id", project_id)
            .order("updated_at", desc=True)
            .execute()
        )

        chats = response.data or []
        for chat in chats:
            msgs_response = (
                self.supabase.table(self.messages_table)
                .select("role, content")
                .eq("chat_id", chat["id"])
                .execute()
            )
            chat["message_count"] = sum(
                1 for m in (msgs_response.data or []) if self._is_displayable_message(m)
            )
        return chats

    @staticmethod
    def _is_displayable_message(msg: Dict[str, Any]) -> bool:
        """
        True if a message row should appear in the user-visible chat
        transcript. Mirrors the filter `get_chat()` applies when building
        `display_messages` (non-tool roles, non-list content, non-empty
        text). Centralized so the sidebar count and the header count
        can't drift apart.
        """
        if msg.get("role") not in ("user", "assistant"):
            return False
        content = msg.get("content")
        # List-content rows are tool-chain intermediates (assistant
        # tool_use envelopes and user tool_result wrappers).
        if isinstance(content, list):
            return False
        if isinstance(content, dict):
            text = content.get("text", "")
        elif isinstance(content, str):
            text = content
        else:
            text = str(content) if content else ""
        return bool(text.strip())

    def create_chat(self, project_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """
        Create a new chat in a project.

        Educational Note: Initializes an empty conversation with metadata.
        Messages are added separately via message_service.

        Args:
            project_id: The project UUID
            title: Initial chat title

        Returns:
            Created chat metadata
        """
        chat_data = {
            "project_id": project_id,
            "title": title
        }

        response = (
            self.supabase.table(self.table)
            .insert(chat_data)
            .execute()
        )

        if response.data:
            chat = response.data[0]
            return {
                "id": chat["id"],
                "title": chat["title"],
                "created_at": chat["created_at"],
                "updated_at": chat["updated_at"],
                "message_count": 0
            }

        raise RuntimeError("Failed to create chat")

    def get_chat(self, project_id: str, chat_id: str, include_raw: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get full chat data including messages and studio signals.

        Educational Note: Filters out tool_use and tool_result messages
        from the response by default. When include_raw=True, returns ALL
        messages with their original content blocks for debug/raw view.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            include_raw: If True, include all messages with original content

        Returns:
            Full chat data or None if not found
        """
        # Get chat metadata
        chat_response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not chat_response.data:
            return None

        chat = chat_response.data[0]

        # Get messages for this chat
        messages_response = (
            self.supabase.table(self.messages_table)
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )

        messages = messages_response.data or []

        if include_raw:
            # Raw mode: return ALL messages with original content and derived type
            display_messages = []
            for msg in messages:
                content = msg.get("content")
                role = msg.get("role")
                message_type = self._derive_message_type(role, content)
                display_messages.append({
                    "id": msg.get("id"),
                    "role": role,
                    "content": content,  # Original JSONB (string, dict, or list)
                    "message_type": message_type,
                    "created_at": msg.get("created_at"),
                    "model": msg.get("model"),
                })
        else:
            # Normal mode: filter out tool chain intermediates
            # Educational Note: During a tool_use loop, main_chat_service stores:
            #   1. Intermediate assistant messages with LIST content (serialized content
            #      blocks containing text + tool_use blocks)
            #   2. Tool_result user messages with LIST content
            #   3. Final assistant message with DICT content ({"text": "..."})
            # The final message already contains all accumulated text from the tool
            # chain, so intermediate list-content messages must be skipped to avoid
            # showing duplicate responses.
            display_messages = []
            for msg in messages:
                content = msg.get("content")
                role = msg.get("role")

                if role not in ["user", "assistant"]:
                    continue

                # Skip list-content messages — these are tool chain intermediates
                # (tool_use assistant responses and tool_result user messages)
                if isinstance(content, list):
                    continue

                if isinstance(content, dict):
                    text_content = content.get("text", "")
                elif isinstance(content, str):
                    text_content = content
                else:
                    text_content = str(content) if content else ""

                if not text_content.strip():
                    continue

                # Create a clean message object for frontend
                display_messages.append({
                    "id": msg.get("id"),
                    "role": role,
                    "content": text_content,  # Always a string
                    "timestamp": msg.get("created_at"),  # Map created_at to timestamp
                    "model": msg.get("model"),
                    "citations": msg.get("citations", [])
                })

        # Get studio signals
        signals_response = (
            self.supabase.table(self.studio_signals_table)
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )

        # Transform signals for frontend format
        # Backend stores: source_ids: ["uuid1", "uuid2"]
        # Frontend expects: sources: [{source_id: "...", chunk_ids: []}]
        formatted_signals = []
        for signal in (signals_response.data or []):
            source_ids = signal.get("source_ids", []) or []
            formatted_signal = {
                "id": signal.get("id"),
                "studio_item": signal.get("studio_item"),
                "direction": signal.get("direction", ""),
                "sources": [{"source_id": sid, "chunk_ids": []} for sid in source_ids],
                "created_at": signal.get("created_at"),
                "status": signal.get("status", "pending")
            }
            formatted_signals.append(formatted_signal)

        chat["messages"] = display_messages
        chat["studio_signals"] = formatted_signals
        chat["message_count"] = len(messages)

        return chat

    @staticmethod
    def _derive_message_type(role: str, content) -> str:
        """Derive a human-readable message type for the raw view."""
        if role == "user":
            if isinstance(content, list):
                return "tool_result"
            return "user_input"
        if role == "assistant":
            if isinstance(content, list):
                # List content = tool_use blocks from Claude
                has_tool_use = any(
                    isinstance(b, dict) and b.get("type") == "tool_use"
                    for b in content
                )
                return "tool_use" if has_tool_use else "ai_response"
            return "ai_response"
        return "unknown"

    def get_chat_metadata(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chat metadata only (without messages).

        Educational Note: Useful for quick lookups without loading
        the full message history.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            Chat metadata or None if not found
        """
        response = (
            self.supabase.table(self.table)
            .select("id, title, created_at, updated_at")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not response.data:
            return None

        chat = response.data[0]

        # Get message count
        count_response = (
            self.supabase.table(self.messages_table)
            .select("id", count="exact")
            .eq("chat_id", chat_id)
            .execute()
        )
        chat["message_count"] = count_response.count or 0

        return chat

    def update_chat(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update chat metadata.

        Educational Note: Currently supports updating title.
        Messages are updated via message_service.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            updates: Dict of fields to update (e.g., {"title": "New Title"})

        Returns:
            Updated chat metadata or None if not found
        """
        # Check if chat exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not existing.data:
            return None

        # Filter allowed updates
        allowed_fields = ["title", "selected_source_ids"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return self.get_chat_metadata(project_id, chat_id)

        # Update chat
        response = (
            self.supabase.table(self.table)
            .update(filtered_updates)
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if response.data:
            chat = response.data[0]
            # Get message count
            count_response = (
                self.supabase.table(self.messages_table)
                .select("id", count="exact")
                .eq("chat_id", chat_id)
                .execute()
            )
            return {
                "id": chat["id"],
                "title": chat["title"],
                "created_at": chat["created_at"],
                "updated_at": chat["updated_at"],
                "message_count": count_response.count or 0
            }

        return None

    def delete_chat(self, project_id: str, chat_id: str) -> bool:
        """
        Delete a chat and all its messages.

        Educational Note: Supabase cascades deletes automatically based on
        foreign key constraints. Deleting a chat also deletes its messages
        and studio signals.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if deleted, False if not found
        """
        # Check if chat exists
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not existing.data:
            return False

        # Delete the chat (messages and signals cascade automatically)
        self.supabase.table(self.table).delete().eq("id", chat_id).eq("project_id", project_id).execute()

        # Cascade-delete inline chat attachments from storage. The DB
        # cascade only covers tables, not the storage bucket — without
        # this, screenshots pasted into deleted chats would orphan in
        # the chat-attachments bucket forever. Best-effort: a storage
        # failure shouldn't block the DB delete from being reported.
        try:
            from app.services.integrations.supabase import storage_service
            storage_service.delete_chat_attachments_for_chat(project_id, chat_id)
        except Exception as exc:  # pragma: no cover — defensive
            import logging
            logging.getLogger(__name__).warning(
                "Failed to clean chat-attachment storage for %s/%s: %s",
                project_id, chat_id, exc,
            )

        return True

    def sync_chat_to_index(self, project_id: str, chat_id: str) -> bool:
        """
        Sync a chat's metadata (no-op for Supabase version).

        Educational Note: In Supabase, the data is always in sync.
        This method exists for API compatibility.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            True if chat exists
        """
        existing = (
            self.supabase.table(self.table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )
        return bool(existing.data)

    def get_chat_costs(self, project_id: str, chat_id: str) -> Dict[str, Any]:
        """
        Get cost tracking data for a specific chat.

        Educational Note: Mirrors project_service.get_project_costs() —
        returns the costs JSONB column, or a default structure if the chat
        exists but has no costs yet.

        Args:
            project_id: The project UUID (for authorization scoping)
            chat_id: The chat UUID

        Returns:
            Cost dict with total_cost and by_model breakdown
        """
        response = (
            self.supabase.table(self.table)
            .select("costs")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not response.data:
            return {
                "total_cost": 0.0,
                "by_model": {
                    "opus": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
                    "sonnet": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
                    "haiku": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
                },
            }

        return response.data[0].get("costs") or {
            "total_cost": 0.0,
            "by_model": {
                "opus": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
                "sonnet": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
                "haiku": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            },
        }

    def get_chat_sync_state(self, project_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        chat = self.get_chat(project_id, chat_id)
        if not chat:
            return None

        return {
            "chat": {
                "id": chat["id"],
                "title": chat["title"],
                "created_at": chat["created_at"],
                "updated_at": chat["updated_at"],
                "message_count": chat["message_count"],
                "selected_source_ids": chat.get("selected_source_ids"),
            },
            "studio_signals": chat.get("studio_signals", []),
            "chat_costs": self.get_chat_costs(project_id, chat_id),
        }

    def get_chat_costs_raw(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Load raw costs JSONB for a chat by chat_id only (no project scoping).

        Used internally by cost_tracking._load_chat_costs. Returns None if
        the chat doesn't exist — the cost tracker will fall back to defaults.
        """
        response = (
            self.supabase.table(self.table)
            .select("costs")
            .eq("id", chat_id)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0].get("costs")

    def update_chat_costs(self, chat_id: str, costs: Dict[str, Any]) -> str:
        """
        Persist updated costs JSONB to a chat.

        Used internally by cost_tracking._save_chat_costs. Returns one
        of three string sentinels so the caller can distinguish:

        - ``"ok"``: the chat row existed and was updated.
        - ``"missing"``: the UPDATE matched zero rows. This happens
          when a chat is deleted mid-stream — Claude calls continue
          producing tokens (and trying to persist costs) for several
          seconds after the DELETE returns. We don't want to alarm
          the operator with a "Failed to save costs" warning for the
          user-deleted-their-chat case.
        - ``"error"``: PostgREST / network error. The exception is
          logged here and re-surfaced as this sentinel so the caller
          can still WARN.
        """
        try:
            response = (
                self.supabase.table(self.table)
                .update({"costs": costs})
                .eq("id", chat_id)
                .execute()
            )
        except Exception as exc:
            # Log here so the underlying exception isn't swallowed by
            # the bool-return downstream consumer; cost tracking's
            # warning is intentionally short.
            logger.error("update_chat_costs failed for %s: %s", chat_id, exc)
            return "error"
        return "ok" if response.data else "missing"


# Singleton instance for easy import
chat_service = ChatService()
