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
        if isinstance(content, dict) and "text" in content:
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

        return {
            "id": message.get("id"),
            "role": message.get("role"),
            "content": text_content,
            "timestamp": message.get("created_at"),
            "model": message.get("model"),
            "citations": message.get("citations", [])
        }

    def add_user_message(
        self,
        project_id: str,
        chat_id: str,
        content: str
    ) -> Optional[Dict[str, Any]]:
        """
        Add a user message to a chat.

        Educational Note: Convenience method for the common case of
        adding a simple text message from the user.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            content: The user's message text

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

        Important: This method also sanitizes the message history to handle
        orphaned tool_use blocks (assistant messages with tool_use that never
        got matching tool_result messages). This can happen if a tool execution
        or database write fails mid-loop. Without sanitization, the Claude API
        rejects the entire conversation with a 400 error.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            include_pending: Optional message to include at the end

        Returns:
            List of message dicts ready for Claude API
        """
        messages = self.get_messages(project_id, chat_id)

        # Convert to API format
        api_messages = []
        for msg in messages:
            content = msg.get("content")
            # If content is a dict with "text" key, extract it for simple messages
            # Otherwise keep the full content (for tool_use/tool_result)
            if isinstance(content, dict) and "text" in content and msg.get("role") in ["user", "assistant"]:
                api_content = content["text"]
            else:
                api_content = content

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

        # Sanitize: ensure every tool_use block has a matching tool_result.
        # Educational Note: The Claude API requires that every assistant message
        # containing tool_use blocks is immediately followed by a user message
        # with tool_result blocks for each tool_use ID. If a previous request
        # crashed mid-loop, the DB may have orphaned tool_use blocks without
        # matching tool_results. We fix this by injecting synthetic error
        # tool_results so the conversation can continue.
        api_messages = self._sanitize_tool_use_pairs(api_messages)

        return api_messages

    @staticmethod
    def _sanitize_tool_use_pairs(
        api_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ensure every tool_use block has a matching tool_result in the next message.

        Educational Note: Scans the message list for assistant messages that
        contain tool_use blocks. For each such message, checks if the immediately
        following user message contains the required tool_result blocks. If any
        tool_use IDs are missing their tool_result, injects a synthetic user
        message with error tool_results before the next message.

        Args:
            api_messages: List of message dicts (role + content)

        Returns:
            Sanitized list with synthetic tool_results injected where needed
        """
        sanitized = []
        i = 0

        while i < len(api_messages):
            msg = api_messages[i]
            sanitized.append(msg)

            # Check if this is an assistant message with tool_use blocks
            if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
                tool_use_ids = [
                    block.get("id")
                    for block in msg["content"]
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id")
                ]

                if tool_use_ids:
                    # Collect all tool_result IDs from subsequent user messages
                    # (there may be multiple user messages, one per tool_result)
                    answered_ids = set()
                    j = i + 1
                    while j < len(api_messages) and api_messages[j].get("role") == "user":
                        next_content = api_messages[j].get("content")
                        if isinstance(next_content, list):
                            for block in next_content:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    answered_ids.add(block.get("tool_use_id"))
                        j += 1

                    # Find orphaned tool_use IDs
                    missing_ids = [tid for tid in tool_use_ids if tid not in answered_ids]

                    if missing_ids:
                        logger.warning(
                            "Sanitizing %d orphaned tool_use block(s) in chat history: %s",
                            len(missing_ids),
                            missing_ids,
                        )
                        # Inject synthetic tool_result for each missing ID
                        synthetic_results = [
                            {
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": "Error: tool execution was interrupted. Please retry if needed.",
                                "is_error": True,
                            }
                            for tid in missing_ids
                        ]
                        # Insert right after the current assistant message
                        sanitized.append({
                            "role": "user",
                            "content": synthetic_results,
                        })

            i += 1

        return sanitized

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
