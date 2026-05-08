"""
Message Service - Handles message persistence and retrieval for chat conversations.

Educational Note: This is a pure CRUD service for messages using Supabase.
It handles storing and retrieving messages, building message arrays for API calls.

Key Responsibilities:
- Store messages to Supabase messages table
- Retrieve message history
- Build message arrays for Claude API calls
- Support different message types (user, assistant, tool_result)
- Store and retrieve agent execution logs (local files for debugging)

For parsing Claude API responses (tool_use blocks, content extraction),
see utils/claude_parsing_utils.py
"""
import base64
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from config import Config
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_web_agent_dir, get_agents_dir
import logging

from app.services.integrations.supabase import get_supabase, is_supabase_enabled

logger = logging.getLogger(__name__)


class MessageService:
    """
    Service class for message persistence using Supabase.

    Educational Note: Messages are stored in the Supabase messages table.
    This service handles the format conversion between storage and API.
    """

    def __init__(self):
        """Initialize the message service."""
        if not is_supabase_enabled():
            raise RuntimeError(
                "Supabase is not configured. Please add SUPABASE_URL and "
                "SUPABASE_ANON_KEY to your .env file."
            )
        self.supabase = get_supabase()
        self.table = "messages"
        self.chats_table = "chats"
        # Keep local storage for agent execution logs (debugging only)
        self.projects_dir = Config.PROJECTS_DIR

    def get_messages(self, project_id: str, chat_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages from a chat.

        Args:
            project_id: The project UUID (used for validation)
            chat_id: The chat UUID

        Returns:
            List of message dicts
        """
        chat_check = (
            self.supabase.table(self.chats_table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )
        if not chat_check.data:
            return []

        response = (
            self.supabase.table(self.table)
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []

    def add_message(
        self,
        project_id: str,
        chat_id: str,
        role: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Add a message to a chat.

        Educational Note: This handles different content types:
        - String content for simple user/assistant messages
        - List content for tool_use/tool_result blocks

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            role: Message role ('user' or 'assistant')
            content: Message content (string or list of content blocks)
            metadata: Optional metadata (model, tokens, error, etc.)

        Returns:
            The created message dict, or None if chat not found
        """
        # Verify chat exists
        chat_check = (
            self.supabase.table(self.chats_table)
            .select("id")
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        if not chat_check.data:
            return None

        # Prepare content for JSONB storage
        # If content is a string, wrap it in a dict for consistency
        if isinstance(content, str):
            db_content = {"text": content}
        else:
            db_content = content

        # Store error flag inside the JSONB content so build_api_messages
        # can filter these out and never send them to Claude.
        if metadata and metadata.get("error"):
            if isinstance(db_content, dict):
                db_content = {**db_content, "error": True}

        # Create message data
        message_data = {
            "chat_id": chat_id,
            "role": role,
            "content": db_content
        }

        # Add optional metadata
        if metadata:
            if "model" in metadata:
                message_data["model"] = metadata["model"]
            if "tokens" in metadata:
                message_data["tokens_input"] = metadata["tokens"].get("input", 0)
                message_data["tokens_output"] = metadata["tokens"].get("output", 0)
            if "citations" in metadata:
                message_data["citations"] = metadata["citations"]
            if "cost_usd" in metadata:
                message_data["cost_usd"] = metadata["cost_usd"]

        # Insert message
        response = (
            self.supabase.table(self.table)
            .insert(message_data)
            .execute()
        )

        if response.data:
            message = response.data[0]
            # Update chat's updated_at timestamp
            self.supabase.table(self.chats_table).update({
                "updated_at": datetime.now().isoformat()
            }).eq("id", chat_id).eq("project_id", project_id).execute()

            # Format message for frontend (extract text from JSONB)
            return self._format_message_for_frontend(message)

        return None

    def _format_message_for_frontend(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a message for frontend consumption.

        Educational Note: Content is stored as JSONB {"text": "..."} in Supabase
        but frontend expects a plain string. This extracts the text.

        Args:
            message: Raw message from Supabase

        Returns:
            Message with content as string
        """
        content = message.get("content")

        # Extract text from JSONB format
        # Educational Note: Content can be stored as:
        # - {"text": "..."} for simple messages
        # - A string (legacy)
        # - A list of content blocks (tool_use responses from Claude)
        #   e.g. [{"type": "text", "text": "..."}, {"type": "tool_use", ...}]
        # If the user attached inline images, the persisted content is a
        # list with `{"type":"image","storage_path":...}` blocks. We surface
        # those to the frontend as a typed-block list so the chat UI can
        # render the image inline; pure-text messages keep the legacy
        # string shape so existing renderers don't have to change.
        has_image_blocks = (
            isinstance(content, list)
            and any(
                isinstance(b, dict) and b.get("type") == "image"
                for b in content
            )
        )

        if has_image_blocks:
            text_content = self._format_blocks_with_images(content)
        elif isinstance(content, dict) and "text" in content:
            text_content = content["text"]
        elif isinstance(content, str):
            text_content = content
        elif isinstance(content, list):
            # Extract only text blocks, skip tool_use/tool_result blocks
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            text_content = "\n\n".join(part for part in text_parts if part.strip())
        else:
            text_content = str(content) if content else ""

        raw_content = message.get("content")
        is_error = isinstance(raw_content, dict) and raw_content.get("error", False)

        return {
            "id": message.get("id"),
            "role": message.get("role"),
            "content": text_content,
            "timestamp": message.get("created_at"),
            "model": message.get("model"),
            "citations": message.get("citations", []),
            "error": is_error,
        }

    def _format_blocks_with_images(self, content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Project a persisted user-message content list down to the shape the
        frontend renderer wants: a list of {type, ...} blocks with image
        URLs re-signed at read time. Internal-only fields (storage_path)
        and tool blocks are stripped.
        """
        # Lazy-import to avoid a circular dependency between message_service
        # (data layer) and storage_service (integration layer).
        from app.services.integrations.supabase import storage_service

        rendered: List[Dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "image":
                storage_path = block.get("storage_path")
                if not storage_path:
                    # Frontend-supplied image (e.g. blob URL during optimistic
                    # render) — pass URL straight through if present.
                    if block.get("url"):
                        rendered.append({
                            "type": "image",
                            "url": block["url"],
                            "media_type": block.get("media_type", "image/png"),
                            "filename": block.get("filename", "attachment"),
                        })
                    continue
                signed_url = storage_service.get_chat_attachment_url(storage_path) or ""
                rendered.append({
                    "type": "image",
                    "url": signed_url,
                    "media_type": block.get("media_type", "image/png"),
                    "filename": block.get("filename", "attachment"),
                })
            elif btype == "text":
                text_value = block.get("text", "")
                if text_value:
                    rendered.append({"type": "text", "text": text_value})
            # Skip tool_use / tool_result / unknown block types — they
            # belong to internal agent flow, not user-visible content.
        return rendered

    def add_user_message(
        self,
        project_id: str,
        chat_id: str,
        content: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Add a user message to a chat.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            content: Either a plain text string (legacy / no-attachment
                path) or a list of content blocks `[{type:"image",
                storage_path:...}, {type:"text", text:"..."}]` for
                messages with inline image attachments. Both shapes
                round-trip through JSONB storage and re-emerge correctly
                via `_format_message_for_frontend` and
                `build_api_messages`.

        Returns:
            The created message dict
        """
        return self.add_message(project_id, chat_id, "user", content)

    def add_assistant_message(
        self,
        project_id: str,
        chat_id: str,
        content: str,
        model: Optional[str] = None,
        tokens: Optional[Dict[str, int]] = None,
        error: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Add an assistant message to a chat.

        Educational Note: Includes metadata about the model and token usage
        for tracking and debugging purposes.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            content: The assistant's response text
            model: Model used to generate response
            tokens: Token usage dict with 'input' and 'output'
            error: Whether this is an error message

        Returns:
            The created message dict
        """
        metadata = {}
        if model:
            metadata["model"] = model
        if tokens:
            metadata["tokens"] = tokens
        if error:
            metadata["error"] = True

        return self.add_message(project_id, chat_id, "assistant", content, metadata)

    def add_tool_result_message(
        self,
        project_id: str,
        chat_id: str,
        tool_use_id: str,
        result: Any,
        is_error: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Add a tool result message to a chat.

        Educational Note: After Claude requests a tool use, we need to
        send back the result. This is a user message with tool_result content.
        Uses claude_parsing_utils for content block building.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            tool_use_id: The ID from the tool_use block
            result: The tool execution result
            is_error: Whether the tool execution failed

        Returns:
            The created message dict
        """
        # Use claude_parsing_utils to build the tool_result content block
        content = claude_parsing_utils.build_single_tool_result(
            tool_use_id=tool_use_id,
            result=str(result) if not isinstance(result, str) else result,
            is_error=is_error
        )
        return self.add_message(project_id, chat_id, "user", content)

    def build_api_messages(
        self,
        project_id: str,
        chat_id: str,
        include_pending: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Build message array for Claude API call.

        Educational Note: The Claude API expects messages in a specific format.
        This method converts stored messages to the API format, optionally
        including a pending message that hasn't been saved yet.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            include_pending: Optional message to include at the end

        Returns:
            List of message dicts ready for Claude API
        """
        messages = self.get_messages(project_id, chat_id)

        # Convert to API format, skipping error messages.
        # Error messages are internal UI feedback (e.g. "overloaded, try again").
        # Sending them to Claude as assistant responses confuses it and can cause
        # follow-up requests to fail or behave strangely.
        api_messages = []
        for msg in messages:
            content = msg.get("content")

            # Skip error messages — flagged via {"error": true} in the JSONB content
            if isinstance(content, dict) and content.get("error"):
                continue

            # If content is a dict with "text" key, extract it for simple messages
            # Otherwise keep the full content (for tool_use/tool_result)
            if isinstance(content, dict) and "text" in content and msg.get("role") in ["user", "assistant"]:
                api_content = content["text"]
            else:
                api_content = content

            # Persisted image blocks reference {storage_path, media_type, ...}
            # — Claude's vision API needs base64-inline source. Rewrite
            # before sending. No-op for messages that have no image blocks.
            api_content = self._rewrite_image_blocks_for_claude(api_content)

            api_messages.append({
                "role": msg["role"],
                "content": api_content
            })

        # Add pending message if provided
        if include_pending:
            api_messages.append({
                "role": include_pending["role"],
                "content": include_pending["content"]
            })

        # Sanitize: fix orphaned tool_use/tool_result sequences from past errors
        api_messages = self._sanitize_tool_sequences(api_messages)

        # Safety guard: Claude API requires messages to end with a user message.
        # If sanitization left trailing assistant messages (from orphaned tool_use
        # or error messages), strip them to prevent 400 errors.
        # Also delete those rows from the DB so the chat self-heals — future requests
        # won't need to re-sanitize the same corrupted tail.
        trailing_assistant_ids = []
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                trailing_assistant_ids.append(msg["id"])
            else:
                break

        while api_messages and api_messages[-1]["role"] == "assistant":
            api_messages.pop()

        if trailing_assistant_ids:
            try:
                self.supabase.table(self.table).delete().in_("id", trailing_assistant_ids).execute()
                logger.info(
                    "Self-healed chat %s: deleted %d trailing assistant messages from DB",
                    chat_id, len(trailing_assistant_ids)
                )
            except Exception as e:
                logger.warning("Failed to self-heal chat %s DB trailing messages: %s", chat_id, e)

        # Also ensure messages start with a user message
        while api_messages and api_messages[0]["role"] != "user":
            api_messages.pop(0)

        return api_messages

    def _rewrite_image_blocks_for_claude(self, content: Any) -> Any:
        """
        Translate persisted image blocks (`{type:"image", storage_path:...}`)
        into Anthropic's vision content shape:
        `{type:"image", source:{type:"base64", media_type, data}}`.

        Non-list content and lists without image blocks pass through
        unchanged so the existing tool-use plumbing still works.

        Failure mode: if a referenced attachment can't be downloaded, the
        image block is dropped (logged) rather than crashing the whole
        request — Claude still gets the user's text.
        """
        if not isinstance(content, list):
            return content
        if not any(
            isinstance(b, dict) and b.get("type") == "image" and b.get("storage_path")
            for b in content
        ):
            return content

        from app.services.integrations.supabase import storage_service

        rewritten: List[Any] = []
        for block in content:
            if not isinstance(block, dict):
                rewritten.append(block)
                continue
            if block.get("type") == "image" and block.get("storage_path"):
                data = storage_service.download_chat_attachment(block["storage_path"])
                if data is None:
                    # Already-logged in storage_service; just skip the image
                    # so the rest of the message still goes through.
                    continue
                rewritten.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": block.get("media_type", "image/png"),
                        "data": base64.standard_b64encode(data).decode("ascii"),
                    },
                })
            else:
                rewritten.append(block)
        return rewritten

    def _sanitize_tool_sequences(self, api_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fix broken tool_use/tool_result sequences in message history.

        Educational Note: The Claude API requires every tool_use block to have a
        matching tool_result in the next message. If a tool execution error left
        orphaned tool_use blocks in the DB, this method strips them so the chat
        can continue working.

        Steps:
        1. Strip tool_use blocks that don't have matching tool_results
        2. Remove user messages that contain only orphaned tool_results
        3. Merge consecutive same-role messages (can happen after stripping)
        """
        if not api_messages:
            return api_messages

        # --- Step 1: Find which tool_use IDs have valid tool_result matches ---
        valid_tool_use_ids: set = set()
        for i, msg in enumerate(api_messages):
            if msg["role"] != "assistant" or not isinstance(msg["content"], list):
                continue
            tool_use_ids = {
                block["id"] for block in msg["content"]
                if isinstance(block, dict) and block.get("type") == "tool_use"
            }
            if not tool_use_ids:
                continue
            # Collect tool_result IDs from subsequent user messages
            result_ids: set = set()
            for j in range(i + 1, len(api_messages)):
                next_msg = api_messages[j]
                if next_msg["role"] == "user" and isinstance(next_msg["content"], list):
                    for block in next_msg["content"]:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            result_ids.add(block.get("tool_use_id"))
                else:
                    break  # Stop at first non-tool-result message
            # Valid only if ALL tool_use IDs have matching results
            if tool_use_ids.issubset(result_ids):
                valid_tool_use_ids.update(tool_use_ids)

        # --- Step 2: Filter out orphaned tool_use and tool_result blocks ---
        filtered: List[Dict[str, Any]] = []
        for msg in api_messages:
            if msg["role"] == "assistant" and isinstance(msg["content"], list):
                has_tool_use = any(
                    isinstance(b, dict) and b.get("type") == "tool_use"
                    for b in msg["content"]
                )
                if has_tool_use:
                    # Keep only valid tool_use blocks and all non-tool_use blocks
                    cleaned = [
                        block for block in msg["content"]
                        if not (isinstance(block, dict) and block.get("type") == "tool_use")
                        or block.get("id") in valid_tool_use_ids
                    ]
                    # Extract text if only text blocks remain
                    if cleaned and all(isinstance(b, dict) and b.get("type") == "text" for b in cleaned):
                        text = "\n".join(b.get("text", "") for b in cleaned).strip()
                        if text:
                            filtered.append({"role": "assistant", "content": text})
                    elif cleaned:
                        filtered.append({"role": "assistant", "content": cleaned})
                    # If empty after cleaning, skip the message entirely
                    continue

            if msg["role"] == "user" and isinstance(msg["content"], list):
                has_tool_result = any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in msg["content"]
                )
                if has_tool_result:
                    # Keep only tool_results with valid IDs
                    cleaned = [
                        block for block in msg["content"]
                        if not (isinstance(block, dict) and block.get("type") == "tool_result")
                        or block.get("tool_use_id") in valid_tool_use_ids
                    ]
                    if cleaned:
                        filtered.append({"role": "user", "content": cleaned})
                    # If empty, skip (orphaned tool_result message)
                    continue

            filtered.append(msg)

        # --- Step 3: Merge consecutive same-role messages ---
        merged: List[Dict[str, Any]] = []
        for msg in filtered:
            if merged and merged[-1]["role"] == msg["role"]:
                prev_content = merged[-1]["content"]
                curr_content = msg["content"]
                # Merge two text strings
                if isinstance(prev_content, str) and isinstance(curr_content, str):
                    merged[-1]["content"] = prev_content + "\n\n" + curr_content
                elif isinstance(prev_content, list) and isinstance(curr_content, list):
                    # Merge two list messages (e.g. multiple tool_result blocks)
                    merged[-1]["content"] = prev_content + curr_content
                else:
                    # Mixed types — skip merging, keep as-is to avoid breaking content blocks
                    merged.append(msg)
            else:
                merged.append(msg)

        return merged

    def build_context_from_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Build API message array from a list of messages.

        Educational Note: This is useful for subagents or other flows
        that don't use stored chat messages but need to build context.

        Args:
            messages: List of message dicts

        Returns:
            List of message dicts ready for Claude API
        """
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]

    def update_chat_metadata(
        self,
        project_id: str,
        chat_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update chat metadata (not messages).

        Educational Note: Used for updating things like title, source_references,
        sub_agents metadata without modifying messages.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            updates: Dict of fields to update

        Returns:
            True if successful
        """
        # Filter to allowed fields
        allowed_fields = ["title"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return True

        response = (
            self.supabase.table(self.chats_table)
            .update(filtered_updates)
            .eq("id", chat_id)
            .eq("project_id", project_id)
            .execute()
        )

        return bool(response.data)

    # =========================================================================
    # Agent Execution Logs - For storing agent debug/execution data
    # (Kept as local files for debugging - not migrated to Supabase)
    # =========================================================================

    def _get_agent_dir(self, project_id: str, agent_name: str) -> Path:
        """
        Get the directory for a specific agent's execution logs.

        Educational Note: Uses path_utils for centralized path management.
        Currently supports 'web_agent', can be extended for other agents.

        Args:
            project_id: The project UUID
            agent_name: The agent name (e.g., 'web_agent')

        Returns:
            Path to agent's execution log directory (auto-created)
        """
        if agent_name == "web_agent":
            return get_web_agent_dir(project_id)
        else:
            # Generic fallback for future agents
            agents_dir = get_agents_dir(project_id)
            agent_dir = agents_dir / agent_name
            agent_dir.mkdir(parents=True, exist_ok=True)
            return agent_dir

    def save_agent_execution(
        self,
        project_id: str,
        agent_name: str,
        execution_id: str,
        task: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Save an agent execution log (local file for debugging).

        Educational Note: Agent execution logs are stored locally for debugging.
        They capture the full message chain, tool calls, and results.

        Structure: data/projects/{project_id}/agents/{agent_name}/{execution_id}.json

        Args:
            project_id: The project UUID
            agent_name: The agent name (e.g., 'web_agent')
            execution_id: Unique execution ID
            task: The task description that was given to the agent
            messages: Full message chain (includes tool_use, tool_result, etc.)
            result: Final result from the agent
            started_at: Execution start timestamp (ISO format)
            metadata: Optional additional metadata (source_id, url, etc.)

        Returns:
            The execution_id if successful, None if failed
        """
        if not project_id:
            return None

        try:
            # Get agent directory using path_utils
            agent_dir = self._get_agent_dir(project_id, agent_name)

            # Build execution log
            execution_log = {
                "execution_id": execution_id,
                "agent_name": agent_name,
                "task": task,
                "messages": messages,
                "result": result,
                "started_at": started_at,
                "completed_at": datetime.now().isoformat()
            }

            # Add optional metadata
            if metadata:
                execution_log.update(metadata)

            # Save to file
            log_file = agent_dir / f"{execution_id}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(execution_log, f, indent=2, ensure_ascii=False)

            return execution_id

        except Exception as e:
            logger.error("Failed to save %s execution log: %s", agent_name, e)
            return None

    def get_agent_execution(
        self,
        project_id: str,
        agent_name: str,
        execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific agent execution log.

        Args:
            project_id: The project UUID
            agent_name: The agent name (e.g., 'web_agent')
            execution_id: The execution UUID

        Returns:
            Execution log dict or None if not found
        """
        try:
            agent_dir = self._get_agent_dir(project_id, agent_name)
            log_file = agent_dir / f"{execution_id}.json"

            if not log_file.exists():
                return None

            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)

        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to read %s execution log: %s", agent_name, e)
            return None

    def list_agent_executions(
        self,
        project_id: str,
        agent_name: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List agent execution logs for a project.

        Educational Note: Returns basic metadata for each execution without
        loading the full message chains. Sorted by completion time (newest first).

        Args:
            project_id: The project UUID
            agent_name: The agent name (e.g., 'web_agent')
            limit: Maximum number of executions to return

        Returns:
            List of execution summaries (id, task, completed_at, success)
        """
        try:
            agent_dir = self._get_agent_dir(project_id, agent_name)

            if not agent_dir.exists():
                return []

            executions = []
            for log_file in agent_dir.glob("*.json"):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        log = json.load(f)
                        executions.append({
                            "execution_id": log.get("execution_id"),
                            "task": log.get("task", "")[:100],  # Truncate task
                            "completed_at": log.get("completed_at"),
                            "success": log.get("result", {}).get("success", False)
                        })
                except (json.JSONDecodeError, IOError):
                    continue

            # Sort by completion time (newest first)
            executions.sort(key=lambda x: x.get("completed_at", ""), reverse=True)

            return executions[:limit]

        except Exception as e:
            logger.error("Failed to list %s executions: %s", agent_name, e)
            return []


# Singleton instance for easy import
message_service = MessageService()
