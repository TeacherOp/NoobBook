"""
Message Service - Handles message persistence and retrieval for chat and agent conversations.

Educational Note: This is a pure CRUD service for messages (chat and agent).
It handles storing and retrieving messages, building message arrays for API calls.
Data access is delegated to the repository layer.

Key Responsibilities:
- Store messages to storage (via repository)
- Retrieve message history
- Build message arrays for Claude API calls
- Support different message types (user, assistant, tool_result)
- Store and retrieve agent execution logs (web_agent, etc.)

For parsing Claude API responses (tool_use blocks, content extraction),
see utils/claude_parsing_utils.py
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any

from app.repositories import get_message_repository
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_web_agent_dir, get_agents_dir


class MessageService:
    """
    Service class for message persistence and context management.

    Educational Note: Messages are stored via the repository layer.
    This service handles the format conversion between storage and API.
    """

    def __init__(self):
        """Initialize the message service."""
        self._repo = None

    @property
    def repo(self):
        """Lazy-load the repository."""
        if self._repo is None:
            self._repo = get_message_repository()
        return self._repo

    def get_messages(self, project_id: str, chat_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages from a chat.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID

        Returns:
            List of message dicts
        """
        return self.repo.get_by_chat(project_id, chat_id)

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
        return self.repo.add_message(
            project_id=project_id,
            chat_id=chat_id,
            role=role,
            content=content,
            metadata=metadata
        )

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
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Add pending message if provided
        if include_pending:
            api_messages.append({
                "role": include_pending["role"],
                "content": include_pending["content"]
            })

        return api_messages

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
        return self.repo.update_chat_metadata(project_id, chat_id, updates)

    # =========================================================================
    # Agent Execution Logs - For storing agent debug/execution data
    # =========================================================================

    def _get_agent_dir(self, project_id: str, agent_name: str):
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
        Save an agent execution log.

        Educational Note: Agent execution logs are stored separately from chat
        messages. They capture the full message chain, tool calls, and results
        for debugging and auditing agent behavior.

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
            print(f"  No project_id provided, skipping {agent_name} execution log save")
            return None

        try:
            import json

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

            print(f"  Agent execution log saved: {log_file}")
            return execution_id

        except Exception as e:
            print(f"  Error saving {agent_name} execution log: {e}")
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
            import json

            agent_dir = self._get_agent_dir(project_id, agent_name)
            log_file = agent_dir / f"{execution_id}.json"

            if not log_file.exists():
                return None

            with open(log_file, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            print(f"  Error reading {agent_name} execution log: {e}")
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
            import json

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
                except Exception:
                    continue

            # Sort by completion time (newest first)
            executions.sort(key=lambda x: x.get("completed_at", ""), reverse=True)

            return executions[:limit]

        except Exception as e:
            print(f"  Error listing {agent_name} executions: {e}")
            return []


# Singleton instance for easy import
message_service = MessageService()
