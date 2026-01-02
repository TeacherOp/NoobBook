"""
Main Chat Service - Orchestrates chat message processing and AI responses.

Educational Note: This service handles the core chat logic with tool support.

Message Flow:
1. User message - What the user types in chat
2. Assistant response - Two types:
   a. Text response - Final answer to user (stored and displayed)
   b. Tool use - Claude wants to search sources
3. User message (tool_result) - Results from tool execution sent back
4. Repeat 2-3 until Claude gives text response

The service uses message_service for all message handling and tool parsing.
"""
from typing import Dict, Any, Tuple, List, Optional

from app.services.data_services import chat_service
from app.services.integrations.claude import claude_service
from app.services.data_services import message_service
from app.config import prompt_loader, tool_loader, context_loader
from app.services.tool_executors import source_search_executor
from app.services.tool_executors import memory_executor
from app.services.tool_executors import csv_analyzer_agent_executor
from app.services.tool_executors import studio_signal_executor
from app.services.tool_executors import database_tool_executor
from app.services.ai_services.chat_naming_service import chat_naming_service
from app.services.background_services import task_service
from app.utils import claude_parsing_utils


class MainChatService:
    """
    Service class for orchestrating chat conversations with tool support.

    Educational Note: This service coordinates the message flow between
    user, Claude, and tools. It uses message_service for all message
    operations and tool parsing.
    """

    # Maximum tool iterations to prevent infinite loops
    MAX_TOOL_ITERATIONS = 10

    def __init__(self):
        """Initialize the service."""
        self._search_tool = None
        self._memory_tool = None
        self._csv_analyzer_tool = None
        self._studio_signal_tool = None
        self._database_tool = None

    def _get_search_tool(self) -> Dict[str, Any]:
        """Load the search_sources tool definition (cached)."""
        if self._search_tool is None:
            self._search_tool = tool_loader.load_tool("chat_tools", "source_search_tool")
        return self._search_tool

    def _get_memory_tool(self) -> Dict[str, Any]:
        """Load the store_memory tool definition (cached)."""
        if self._memory_tool is None:
            self._memory_tool = tool_loader.load_tool("chat_tools", "memory_tool")
        return self._memory_tool

    def _get_csv_analyzer_tool(self) -> Dict[str, Any]:
        """Load the analyze_csv_agent tool definition (cached)."""
        if self._csv_analyzer_tool is None:
            self._csv_analyzer_tool = tool_loader.load_tool("chat_tools", "analyze_csv_agent_tool")
        return self._csv_analyzer_tool

    def _get_studio_signal_tool(self) -> Dict[str, Any]:
        """Load the studio_signal tool definition (cached)."""
        if self._studio_signal_tool is None:
            self._studio_signal_tool = tool_loader.load_tool("chat_tools", "studio_signal_tool")
        return self._studio_signal_tool

    def _get_database_tool(self) -> Dict[str, Any]:
        """Load the database_query tool definition (cached)."""
        if self._database_tool is None:
            self._database_tool = tool_loader.load_tool("chat_tools", "database_query_tool")
        return self._database_tool

    def _get_tools(self, has_active_sources: bool, has_csv_sources: bool = False, has_database_connections: bool = False) -> List[Dict[str, Any]]:
        """
        Get tools list for Claude API call.

        Educational Note: Memory and studio_signal tools are always available.
        Search tool is only available when there are active non-CSV sources.
        CSV analyzer tool is available when there are CSV sources.
        Database tool is available when there are connected databases.

        Args:
            has_active_sources: Whether project has active non-CSV sources
            has_csv_sources: Whether project has active CSV sources
            has_database_connections: Whether user has connected databases

        Returns:
            List of tool definitions
        """
        # Always include memory and studio_signal tools
        tools = [
            self._get_memory_tool(),
            self._get_studio_signal_tool()
        ]

        if has_active_sources:
            tools.append(self._get_search_tool())

        if has_csv_sources:
            tools.append(self._get_csv_analyzer_tool())

        if has_database_connections:
            tools.append(self._get_database_tool())

        return tools

    def _build_system_prompt(self, project_id: str, base_prompt: str) -> str:
        """
        Build system prompt with memory and source context appended.

        Educational Note: Context is rebuilt on every message to reflect
        current state (memory updates, active/inactive sources).
        Includes both memory context (personalization) and source context (tools).
        """
        full_context = context_loader.build_full_context(project_id)
        if full_context:
            return base_prompt + "\n" + full_context
        return base_prompt

    def _execute_tool(
        self,
        project_id: str,
        chat_id: str,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """
        Execute a tool and return result string.

        Educational Note: Routes tool calls to appropriate executor.
        - search_sources: Searches project sources for information
        - store_memory: Stores user/project memory (non-blocking, queues background task)
        - analyze_csv_agent: Triggers CSV analyzer agent for CSV data questions
        - studio_signal: Activates studio generation options (non-blocking, queues background task)
        """
        if tool_name == "search_sources":
            result = source_search_executor.execute(
                project_id=project_id,
                source_id=tool_input.get("source_id", ""),
                keywords=tool_input.get("keywords"),
                query=tool_input.get("query")
            )
            if result.get("success"):
                return result.get("content", "No content found")
            else:
                return f"Error: {result.get('error', 'Unknown error')}"

        elif tool_name == "store_memory":
            # Memory tool returns immediately, actual update happens in background
            result = memory_executor.execute(
                project_id=project_id,
                user_memory=tool_input.get("user_memory"),
                project_memory=tool_input.get("project_memory"),
                why_generated=tool_input.get("why_generated", "")
            )
            if result.get("success"):
                return result.get("message", "Memory stored successfully")
            else:
                return f"Error: {result.get('message', 'Unknown error')}"

        elif tool_name == "analyze_csv_agent":
            # CSV analyzer agent for answering questions about CSV data
            result = csv_analyzer_agent_executor.execute(
                project_id=project_id,
                source_id=tool_input.get("source_id", ""),
                query=tool_input.get("query", "")
            )
            if result.get("success"):
                content = result.get("content", "No analysis result")
                # Include image filenames if any plots were generated
                # Educational Note: Filenames are auto-generated unique IDs
                # Main chat Claude MUST use these exact filenames with [[image:FILENAME]]
                if result.get("image_paths"):
                    content += f"\n\nGenerated visualizations (use these exact filenames):\n"
                    for filename in result["image_paths"]:
                        content += f"- [[image:{filename}]]\n"
                return content
            else:
                return f"Error: {result.get('error', 'Analysis failed')}"

        elif tool_name == "studio_signal":
            # Studio signal returns immediately, actual storage happens in background
            result = studio_signal_executor.execute(
                project_id=project_id,
                chat_id=chat_id,
                signals=tool_input.get("signals", [])
            )
            if result.get("success"):
                return result.get("message", "Studio signals activated")
            else:
                return f"Error: {result.get('message', 'Unknown error')}"

        elif tool_name == "query_database":
            # Database query tool for answering questions using connected databases
            result = database_tool_executor(
                tool_call=tool_input,
                project_id=project_id,
                user_id="default_user"  # TODO: Get from auth context
            )
            if result.get("success"):
                content = f"SQL Query: {result.get('sql_query', '')}\n"
                content += f"Summary: {result.get('summary', '')}\n"
                query_results = result.get('results', {})
                if query_results.get('rows'):
                    content += f"Found {query_results.get('row_count', 0)} results"
                return content
            else:
                return f"Error: {result.get('error', 'Database query failed')}"

        else:
            return f"Unknown tool: {tool_name}"

    def send_message(
        self,
        project_id: str,
        chat_id: str,
        user_message_text: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process a user message and get AI response.

        Educational Note: This method handles the complete message flow:
        1. Store user message
        2. Build context and call Claude
        3. If tool_use: execute tool, send result, call again
        4. When text response: store and return

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            user_message_text: The user's message text

        Returns:
            Tuple of (user_message_dict, assistant_message_dict)
        """
        # Verify chat exists
        chat = chat_service.get_chat(project_id, chat_id)
        if not chat:
            raise ValueError("Chat not found")

        # Step 1: Store user message
        user_msg = message_service.add_user_message(project_id, chat_id, user_message_text)

        # Step 2: Get config and build system prompt
        prompt_config = prompt_loader.get_project_prompt_config(project_id)
        base_prompt = prompt_config.get("system_prompt", "")
        system_prompt = self._build_system_prompt(project_id, base_prompt)

        # Step 3: Get tools (memory always available, search for non-CSV, analyzer for CSV)
        active_sources = context_loader.get_active_sources(project_id)
        # Separate CSV sources from other sources
        csv_sources = [s for s in active_sources if s.get("file_extension") == ".csv"]
        non_csv_sources = [s for s in active_sources if s.get("file_extension") != ".csv"]
        
        # Check for database sources
        database_sources = [s for s in active_sources if s.get("type") == "database"]
        
        tools = self._get_tools(
            has_active_sources=bool(non_csv_sources),
            has_csv_sources=bool(csv_sources),
            has_database_connections=bool(database_sources)
        )

        try:
            # Step 4: Build messages and call Claude
            api_messages = message_service.build_api_messages(project_id, chat_id)

            response = claude_service.send_message(
                messages=api_messages,
                system_prompt=system_prompt,
                model=prompt_config.get("model"),
                max_tokens=prompt_config.get("max_tokens"),
                temperature=prompt_config.get("temperature"),
                tools=tools,
                project_id=project_id
            )

            # Step 5: Handle tool use loop
            # Educational Note: When Claude wants to use tools, stop_reason is "tool_use".
            # We must execute tools and send back tool_result for each tool_use block.
            # Important: Claude can respond with text + tool_use together. The text is
            # the response to the user, the tool_use is for background processing.
            # We accumulate text from all responses so we don't lose it.
            iteration = 0
            accumulated_text_parts = []

            while claude_parsing_utils.is_tool_use(response) and iteration < self.MAX_TOOL_ITERATIONS:
                iteration += 1

                # Get tool_use blocks from response (can be multiple for parallel tool calls)
                tool_use_blocks = claude_parsing_utils.extract_tool_use_blocks(response)

                if not tool_use_blocks:
                    break

                # Extract text from this response BEFORE storing
                # Educational Note: Claude can respond with text + tool_use together.
                # The text is the actual response to show the user!
                response_text = claude_parsing_utils.extract_text(response)
                if response_text.strip():
                    accumulated_text_parts.append(response_text)

                # Store the assistant's tool_use response
                # Educational Note: The message chain must be:
                # user -> assistant (tool_use[]) -> user (tool_result[]) -> assistant
                # We must store the tool_use response before the tool_result
                serialized_content = claude_parsing_utils.serialize_content_blocks(
                    response.get("content_blocks", [])
                )
                message_service.add_message(
                    project_id=project_id,
                    chat_id=chat_id,
                    role="assistant",
                    content=serialized_content
                )

                # Execute each tool and add results
                for tool_block in tool_use_blocks:
                    tool_id = tool_block.get("id")
                    tool_name = tool_block.get("name")
                    tool_input = tool_block.get("input", {})

                    print(f"Executing tool: {tool_name} for source: {tool_input.get('source_id', 'unknown')}")

                    # Execute tool
                    result = self._execute_tool(project_id, chat_id, tool_name, tool_input)

                    # Add tool result as user message
                    message_service.add_tool_result_message(
                        project_id=project_id,
                        chat_id=chat_id,
                        tool_use_id=tool_id,
                        result=result
                    )

                # Rebuild messages and call Claude again
                api_messages = message_service.build_api_messages(project_id, chat_id)

                # Debug: Log message count before follow-up API call
                print(f"Follow-up API call: {len(api_messages)} messages")
                if not api_messages:
                    print("ERROR: api_messages is empty!")
                    # Try reloading messages to debug
                    debug_messages = message_service.get_messages(project_id, chat_id)
                    print(f"  Raw messages in chat: {len(debug_messages)}")
                    for i, m in enumerate(debug_messages):
                        print(f"  [{i}] role={m.get('role')}, content_type={type(m.get('content')).__name__}")

                response = claude_service.send_message(
                    messages=api_messages,
                    system_prompt=system_prompt,
                    model=prompt_config.get("model"),
                    max_tokens=prompt_config.get("max_tokens"),
                    temperature=prompt_config.get("temperature"),
                    tools=tools,
                    project_id=project_id
                )

            # Step 6: Store final text response
            # Get text from final response (may be empty if Claude sent text + tool_use earlier)
            final_response_text = claude_parsing_utils.extract_text(response)
            if final_response_text.strip():
                accumulated_text_parts.append(final_response_text)

            # Combine all accumulated text
            # Educational Note: When Claude sends text + tool_use, the text comes first.
            # After tool execution, Claude may respond with more text OR empty (nothing to add).
            # We combine all text parts to show the complete response to the user.
            final_text = "\n\n".join(accumulated_text_parts) if accumulated_text_parts else ""

            assistant_msg = message_service.add_assistant_message(
                project_id=project_id,
                chat_id=chat_id,
                content=final_text if final_text.strip() else "I've processed your request.",
                model=response.get("model"),
                tokens=response.get("usage")
            )

        except Exception as api_error:
            # Store error message
            assistant_msg = message_service.add_assistant_message(
                project_id=project_id,
                chat_id=chat_id,
                content=f"Sorry, I encountered an error: {str(api_error)}",
                error=True
            )

        # Step 7: Sync chat index
        chat_service.sync_chat_to_index(project_id, chat_id)

        # Step 8: Auto-rename chat on first message (background task)
        # Educational Note: We check if the chat had no messages before this one.
        # The naming runs in background so it doesn't block the response.
        if chat.get("message_count", 0) == 0:
            # Submit naming task to background
            task_service.submit_task(
                "chat_naming",
                chat_id,
                self._generate_and_update_chat_title,
                project_id,
                chat_id,
                user_message_text
            )

        return user_msg, assistant_msg

    def _generate_and_update_chat_title(
        self,
        project_id: str,
        chat_id: str,
        user_message: str
    ) -> None:
        """
        Generate and update chat title in background.

        Educational Note: This runs as a background task so it doesn't
        block the main chat response. Uses AI to generate a concise title.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            user_message: The user's first message
        """
        try:
            new_title = chat_naming_service.generate_title(user_message, project_id=project_id)
            if new_title:
                chat_service.update_chat(project_id, chat_id, {"title": new_title})
                print(f"Auto-renamed chat {chat_id} to: {new_title}")
        except Exception as e:
            print(f"Error auto-naming chat {chat_id}: {e}")


# Singleton instance
main_chat_service = MainChatService()
