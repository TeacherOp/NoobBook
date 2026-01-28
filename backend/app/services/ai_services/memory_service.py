"""
Memory Service - Manage user and project memory storage.

Educational Note: This service handles persistent memory storage for the chat system.
Memory is stored in two types:
- User memory: Global preferences and context that persists across all projects (in users table)
- Project memory: Project-specific context that is deleted when the project is deleted (in projects table)

The service uses Haiku AI to intelligently merge new memory with existing memory,
keeping the content concise (max 150 tokens per memory type).

Storage: Supabase (users.memory and projects.memory columns)
"""
from datetime import datetime
from typing import Optional, Dict, Any

from app.services.integrations.claude import claude_service
from app.services.data_services import project_service
from app.config import tool_loader, prompt_loader
from app.utils import claude_parsing_utils


class MemoryService:
    """
    Service for managing user and project memory.

    Educational Note: Memory helps the AI maintain context across conversations.
    - User memory: name, preferences, communication style, general goals
    - Project memory: project goals, milestones, decisions, progress

    Prompt config is loaded from data/prompts/memory_prompt.json
    via prompt_loader for consistency with other AI tools.
    """

    def __init__(self):
        """Initialize the memory service."""
        self._prompt_config: Optional[Dict[str, Any]] = None
        self._tool_def: Optional[Dict[str, Any]] = None

    def _get_prompt_config(self) -> Dict[str, Any]:
        """
        Load and cache the prompt config.

        Educational Note: We cache the config to avoid reading
        the file on every memory update request. Uses prompt_loader
        for consistent prompt loading across all AI tools.
        """
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("memory")
            if self._prompt_config is None:
                raise ValueError("memory_prompt.json not found in data/prompts/")
        return self._prompt_config

    def _load_tool_definition(self) -> Dict[str, Any]:
        """Load the save_memory tool definition."""
        if self._tool_def is None:
            self._tool_def = tool_loader.load_tool("memory_tools", "manage_memory_tool")
        return self._tool_def

    def get_user_memory(self) -> Optional[str]:
        """
        Get the current user memory content from Supabase.

        Returns:
            User memory string or None if no memory exists
        """
        try:
            return project_service.get_user_memory()
        except Exception as e:
            print(f"Error reading user memory: {e}")
            return None

    def get_project_memory(self, project_id: str) -> Optional[str]:
        """
        Get the current project memory content from Supabase.

        Args:
            project_id: The project UUID

        Returns:
            Project memory string or None if no memory exists
        """
        try:
            memory_data = project_service.get_project_memory(project_id)
            if memory_data:
                return memory_data.get("memory")
            return None
        except Exception as e:
            print(f"Error reading project memory: {e}")
            return None

    def _save_user_memory(self, memory: str) -> bool:
        """
        Save user memory to Supabase.

        Args:
            memory: The memory content to save

        Returns:
            True if saved successfully
        """
        try:
            return project_service.update_user_memory(memory)
        except Exception as e:
            print(f"Error saving user memory: {e}")
            return False

    def _save_project_memory(self, project_id: str, memory: str) -> bool:
        """
        Save project memory to Supabase.

        Args:
            project_id: The project UUID
            memory: The memory content to save

        Returns:
            True if saved successfully
        """
        try:
            memory_data = {
                "memory": memory,
                "updated_at": datetime.now().isoformat()
            }
            return project_service.update_project_memory(project_id, memory_data)
        except Exception as e:
            print(f"Error saving project memory: {e}")
            return False

    def _build_user_message(
        self,
        config: Dict[str, Any],
        memory_type: str,
        current_memory: str,
        new_memory: str,
        reason: str
    ) -> str:
        """
        Build user message from prompt config template.

        Educational Note: The user_message template is stored in the prompt config
        file (memory_prompt.json) for consistency across AI tools. This keeps
        all prompt-related content in one place for easy tuning.

        Args:
            config: The prompt config containing user_message template
            memory_type: "user" or "project"
            current_memory: Existing memory content
            new_memory: New memory to incorporate
            reason: Why this update was triggered

        Returns:
            Formatted user message from template
        """
        template = config.get("user_message", "")

        return template.format(
            memory_type=memory_type,
            current_memory=current_memory if current_memory else "(empty - no existing memory)",
            new_memory=new_memory,
            reason=reason
        )

    def update_memory(
        self,
        memory_type: str,
        new_memory: str,
        reason: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update memory by merging new content with existing memory using AI.

        Educational Note: This method uses Haiku AI to intelligently merge
        existing memory with new memory. The AI:
        1. Receives current memory + new memory via templated user message
        2. Creates a merged, condensed version (max 150 tokens)
        3. Returns the result via the save_memory tool
        4. We use claude_parsing_utils to parse the tool response

        Args:
            memory_type: "user" or "project"
            new_memory: New memory content to merge
            reason: Why this memory update was triggered
            project_id: Required if memory_type is "project"

        Returns:
            Dict with success status and updated memory
        """
        # Validate inputs
        if memory_type not in ["user", "project"]:
            return {"success": False, "error": f"Invalid memory_type: {memory_type}"}

        if memory_type == "project" and not project_id:
            return {"success": False, "error": "project_id required for project memory"}

        # Get current memory
        if memory_type == "user":
            current_memory = self.get_user_memory() or ""
        else:
            current_memory = self.get_project_memory(project_id) or ""

        # Load prompt config and tool
        config = self._get_prompt_config()
        tool_def = self._load_tool_definition()

        # Build user message using template from config
        user_message = self._build_user_message(
            config=config,
            memory_type=memory_type,
            current_memory=current_memory,
            new_memory=new_memory,
            reason=reason
        )

        try:
            # Call Haiku AI with the save_memory tool
            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config.get('system_prompt', ''),
                model=config.get('model'),
                max_tokens=config.get('max_tokens'),
                temperature=config.get('temperature'),
                tools=[tool_def],
                project_id=project_id  # Track costs for project memory
            )

            # Use claude_parsing_utils to parse tool calls
            tool_inputs = claude_parsing_utils.extract_tool_inputs(response, "save_memory")

            if not tool_inputs:
                return {
                    "success": False,
                    "error": "AI did not use save_memory tool"
                }

            # Get the first tool input (should only be one)
            tool_input = tool_inputs[0]
            merged_memory = tool_input.get("memory", "")

            if not merged_memory:
                return {
                    "success": False,
                    "error": "AI returned empty memory"
                }

            # Save the merged memory
            if memory_type == "user":
                saved = self._save_user_memory(merged_memory)
            else:
                saved = self._save_project_memory(project_id, merged_memory)

            if saved:
                print(f"Memory updated ({memory_type}): {merged_memory[:50]}...")
                return {
                    "success": True,
                    "memory_type": memory_type,
                    "memory": merged_memory,
                    "previous_memory": current_memory,
                    "model": response.get("model"),
                    "usage": response.get("usage")
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save memory to file"
                }

        except Exception as e:
            print(f"Error updating memory: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def delete_project_memory(self, project_id: str) -> bool:
        """
        Clear project memory in Supabase.

        Educational Note: Called when a project is deleted to clean up
        associated memory. With Supabase, the memory is stored in the
        projects table and will be deleted when the project is deleted.

        Args:
            project_id: The project UUID

        Returns:
            True if cleared successfully
        """
        try:
            # Clear the memory by setting it to empty
            return project_service.update_project_memory(project_id, {})
        except Exception as e:
            print(f"Error clearing project memory: {e}")
            return False


# Singleton instance
memory_service = MemoryService()
