"""
Message Repository Interface - Contract for message data access.

Educational Note: Messages are stored separately from chats for efficiency.
Content can be a string (text messages) or a list of content blocks
(tool_use, tool_result messages for Claude API tool use flow).
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class MessageRepositoryInterface(ABC):
    """Interface for message repository operations."""

    @abstractmethod
    def get_all(self, chat_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a chat in order.

        Args:
            chat_id: The chat UUID

        Returns:
            List of messages ordered by sequence_number
        """
        raise NotImplementedError

    @abstractmethod
    def get_for_api(self, chat_id: str) -> List[Dict[str, Any]]:
        """
        Get messages formatted for Claude API call.

        Educational Note: Returns only role and content fields,
        suitable for passing to Claude API.

        Args:
            chat_id: The chat UUID

        Returns:
            List of {role, content} dicts
        """
        raise NotImplementedError

    @abstractmethod
    def add(
        self,
        chat_id: str,
        role: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a message to a chat.

        Args:
            chat_id: The chat UUID
            role: Message role ('user' or 'assistant')
            content: Message content (string or list of content blocks)
            metadata: Optional metadata (model, tokens, error flag)

        Returns:
            The created message dict
        """
        raise NotImplementedError

    @abstractmethod
    def add_user_message(self, chat_id: str, content: str) -> Dict[str, Any]:
        """
        Add a user message (convenience method).

        Args:
            chat_id: The chat UUID
            content: The user's message text

        Returns:
            The created message dict
        """
        raise NotImplementedError

    @abstractmethod
    def add_assistant_message(
        self,
        chat_id: str,
        content: str,
        model: Optional[str] = None,
        tokens: Optional[Dict[str, int]] = None,
        error: bool = False
    ) -> Dict[str, Any]:
        """
        Add an assistant message.

        Args:
            chat_id: The chat UUID
            content: The assistant's response
            model: Model used to generate response
            tokens: Token usage {input, output}
            error: Whether this is an error message

        Returns:
            The created message dict
        """
        raise NotImplementedError

    @abstractmethod
    def add_tool_result(
        self,
        chat_id: str,
        tool_use_id: str,
        result: Any,
        is_error: bool = False
    ) -> Dict[str, Any]:
        """
        Add a tool result message.

        Educational Note: Tool results are user messages with special
        content format required by Claude API.

        Args:
            chat_id: The chat UUID
            tool_use_id: The ID from the tool_use block
            result: The tool execution result
            is_error: Whether the tool execution failed

        Returns:
            The created message dict
        """
        raise NotImplementedError

    @abstractmethod
    def get_message_count(self, chat_id: str) -> int:
        """
        Get the number of messages in a chat.

        Args:
            chat_id: The chat UUID

        Returns:
            Message count
        """
        raise NotImplementedError

    @abstractmethod
    def delete_chat_messages(self, chat_id: str) -> int:
        """
        Delete all messages for a chat.

        Args:
            chat_id: The chat UUID

        Returns:
            Number of messages deleted
        """
        raise NotImplementedError
