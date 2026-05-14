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
import logging
from typing import Dict, Any, Tuple, List, Optional, Callable, Union


# A user message coming in from the API can be either a plain string
# (legacy / no-attachment path) or a list of content blocks (new path
# with inline image attachments). Both shapes round-trip through
# add_user_message → JSONB storage → build_api_messages.
UserMessagePayload = Union[str, List[Dict[str, Any]]]


def _extract_user_text(content: UserMessagePayload) -> str:
    """
    Pull the plain-text portion out of a user-message payload, supporting
    either a raw string or a content-block list. Used by codepaths that
    want only the user's words (chat naming, studio-signal direction
    override) — they shouldn't see internal image-block metadata.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text")
        )
    return ""

from app.services.data_services import chat_service
from app.services.data_services.user_service import get_user_service

logger = logging.getLogger(__name__)
from app.services.integrations.claude import claude_service
from app.services.data_services import message_service
from app.config import prompt_loader, tool_loader, context_loader, brand_context_loader
from app.services.tool_executors import source_search_executor
from app.services.tool_executors import memory_executor
from app.services.tool_executors import csv_analyzer_agent_executor
from app.services.tool_executors import database_analyzer_agent_executor
from app.services.tool_executors import freshdesk_analyzer_agent_executor
from app.services.tool_executors import studio_signal_executor
from app.services.integrations.knowledge_bases import knowledge_base_service
from app.services.integrations.mcp.mcp_tool_service import mcp_tool_service
from app.services.ai_services.chat_naming_service import chat_naming_service
from app.services.background_services import task_service
from flask import has_request_context
from app.services.auth.rbac import get_request_identity
from app.services.data_services.project_service import DEFAULT_USER_ID
from app.utils import claude_parsing_utils
from app.services.auth.permissions import user_has_permission


class ClaudeStreamError(Exception):
    """Wrap a streaming error with any text that already streamed."""

    def __init__(self, message: str, partial_text: str = ""):
        super().__init__(message)
        self.partial_text = partial_text


class MainChatService:
    """
    Service class for orchestrating chat conversations with tool support.

    Educational Note: This service coordinates the message flow between
    user, Claude, and tools. It uses message_service for all message
    operations and tool parsing.
    """

    # Maximum tool iterations to prevent infinite loops.
    # 40 matches the ceiling used across every other agent in the
    # codebase (database_analyzer, presentation_agent, and now all the
    # rest). Most multi-part chats use far fewer rounds in practice —
    # the synthesis fallback below catches the worst-case
    # "burnt budget with no visible response" mode, so we'd rather give
    # complex questions room to finish than clip them early.
    MAX_TOOL_ITERATIONS = 40

    def __init__(self):
        """Initialize the service."""
        self._search_tool = None
        self._memory_tool = None
        self._csv_analyzer_tool = None
        self._database_analyzer_tool = None
        self._freshdesk_analyzer_tool = None
        self._studio_signal_tool = None

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

    def _get_database_analyzer_tool(self) -> Dict[str, Any]:
        """Load the analyze_database_agent tool definition (cached)."""
        if self._database_analyzer_tool is None:
            self._database_analyzer_tool = tool_loader.load_tool(
                "chat_tools", "analyze_database_agent_tool"
            )
        return self._database_analyzer_tool

    def _get_freshdesk_analyzer_tool(self) -> Dict[str, Any]:
        """Load the analyze_freshdesk_agent tool definition (cached)."""
        if self._freshdesk_analyzer_tool is None:
            self._freshdesk_analyzer_tool = tool_loader.load_tool(
                "chat_tools", "analyze_freshdesk_agent_tool"
            )
        return self._freshdesk_analyzer_tool

    def _get_studio_signal_tool(self) -> Dict[str, Any]:
        """Load the studio_signal tool definition (cached)."""
        if self._studio_signal_tool is None:
            self._studio_signal_tool = tool_loader.load_tool("chat_tools", "studio_signal_tool")
        return self._studio_signal_tool

    def _get_tools(
        self,
        has_active_sources: bool,
        has_csv_sources: bool = False,
        has_database_sources: bool = False,
        has_freshdesk_sources: bool = False,
        has_jira_sources: bool = False,
        has_mixpanel_sources: bool = False,
        user_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict]:
        """
        Get tools list for Claude API call.

        Educational Note: Memory and studio_signal tools are always available.
        Search tool is only available when there are active non-CSV sources.
        CSV analyzer tool is available when there are CSV sources.
        Database analyzer tool is available when there are DATABASE sources.
        Freshdesk analyzer tool is available when there are FRESHDESK sources.
        Jira tools are available when the project has a .jira source (project-scoped).
        Non-Jira knowledge base tools (Notion, GitHub) are added if configured.
        MCP tools are added if the user has tool-enabled MCP connections.

        Args:
            has_active_sources: Whether project has active non-CSV sources
            has_csv_sources: Whether project has active CSV sources
            has_database_sources: Whether project has active DATABASE sources
            has_freshdesk_sources: Whether project has active FRESHDESK sources
            has_jira_sources: Whether project has active JIRA sources
            has_mixpanel_sources: Whether project has active MIXPANEL sources
            user_id: The requesting user's ID (for MCP tool access)

        Returns:
            Tuple of (tool definitions list, MCP tool registry dict)
        """
        # Include memory and studio_signal tools only if the user has permission
        tools = []

        if not user_id or user_has_permission(user_id, "chat_features", "memory"):
            tools.append(self._get_memory_tool())

        if not user_id or user_has_permission(user_id, "studio"):
            tools.append(self._get_studio_signal_tool())

        if has_active_sources:
            tools.append(self._get_search_tool())

        if has_csv_sources and (not user_id or user_has_permission(user_id, "data_sources", "csv")):
            tools.append(self._get_csv_analyzer_tool())

        if has_database_sources and (not user_id or user_has_permission(user_id, "data_sources", "database")):
            tools.append(self._get_database_analyzer_tool())

        if has_freshdesk_sources and (not user_id or user_has_permission(user_id, "data_sources", "freshdesk")):
            tools.append(self._get_freshdesk_analyzer_tool())

        # Add Jira tools only when the project has a .jira source (project-scoped)
        if has_jira_sources and (not user_id or user_has_permission(user_id, "data_sources", "jira")):
            tools.extend(knowledge_base_service.get_jira_tools())

        # Add Mixpanel tools only when the project has a .mixpanel source (project-scoped)
        if has_mixpanel_sources and (not user_id or user_has_permission(user_id, "data_sources", "mixpanel")):
            tools.extend(knowledge_base_service.get_mixpanel_tools())

        # Add non-Jira knowledge base tools (Notion, GitHub, etc.) — always global
        tools.extend(knowledge_base_service.get_available_tools())

        # Add MCP tools if user has tool-enabled connections
        mcp_registry: Dict = {}
        if user_id:
            try:
                mcp_tools, mcp_registry = mcp_tool_service.get_available_tools(user_id=user_id)
                if mcp_tools:
                    tools.extend(mcp_tools)
                    logger.info("Added %d MCP tools for user %s", len(mcp_tools), user_id)
            except Exception as e:
                logger.error("Failed to load MCP tools for user %s: %s", user_id, e)

        return tools, mcp_registry

    def _build_system_prompt(
        self,
        project_id: str,
        base_prompt: str,
        user_id: Optional[str] = None,
        selected_source_ids: Optional[List[str]] = None,
    ) -> str:
        """
        Build system prompt with memory and source context appended.

        Educational Note: Context is rebuilt on every message to reflect
        current state (memory updates, per-chat source selections).
        Includes both memory context (personalization) and source context (tools).
        """
        # Prepend today's date so Claude can compute "yesterday", "last week",
        # etc. accurately when users ask for analytics without explicit dates.
        from datetime import date
        today_line = f"Today's date: {date.today().isoformat()}"
        parts = [today_line, base_prompt]

        full_context = context_loader.build_full_context(
            project_id, user_id=user_id, selected_source_ids=selected_source_ids
        )
        if full_context:
            parts.append(full_context)

        # Inject brand guidelines so the chat AI can follow brand colors, voice, etc.
        brand_context = brand_context_loader.load_brand_context(project_id, "chat", user_id=user_id)
        if brand_context:
            parts.append(brand_context)

        return "\n".join(parts)

    def _execute_tool(
        self,
        project_id: str,
        chat_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        user_id: Optional[str] = None,
        mcp_registry: Optional[Dict] = None,
        user_message_text: Optional[str] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
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
                why_generated=tool_input.get("why_generated", ""),
                user_id=user_id,
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
                query=tool_input.get("query", ""),
                chat_id=chat_id,
                user_id=user_id,
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

        elif tool_name == "analyze_database_agent":
            # Database analyzer agent for answering questions using live SQL
            result = database_analyzer_agent_executor.execute(
                project_id=project_id,
                source_id=tool_input.get("source_id", ""),
                query=tool_input.get("query", ""),
                chat_id=chat_id,
                user_id=user_id,
            )
            if result.get("success"):
                return result.get("content", "No analysis result")
            else:
                return f"Error: {result.get('error', 'Analysis failed')}"

        elif tool_name == "analyze_freshdesk_agent":
            # Freshdesk analyzer agent for answering questions about ticket data
            result = freshdesk_analyzer_agent_executor.execute(
                project_id=project_id,
                source_id=tool_input.get("source_id", ""),
                query=tool_input.get("query", ""),
                chat_id=chat_id,
                user_id=user_id,
                on_event=on_event,
            )
            if result.get("success"):
                return result.get("content", "No analysis result")
            else:
                return f"Error: {result.get('error', 'Analysis failed')}"

        elif tool_name == "studio_signal":
            # Override every signal's `direction` with the user's verbatim
            # prompt. The studio generators downstream (ad creative service,
            # social posts service, blog agent, etc.) read `direction` as
            # the user's intent — letting Claude paraphrase introduces
            # drift, lost specifics, and hallucinated style notes. The tool
            # description already asks Claude to pass the prompt verbatim;
            # this is the belt-and-braces guarantee.
            signals = tool_input.get("signals", [])
            if user_message_text and isinstance(signals, list):
                # user_message_text can be a content-block list when the
                # user attached an inline image — strip() only works on
                # the text portion, so extract that first.
                stripped = _extract_user_text(user_message_text).strip()
                if stripped:
                    signals = [
                        {**s, "direction": stripped} if isinstance(s, dict) else s
                        for s in signals
                    ]

            result = studio_signal_executor.execute(
                project_id=project_id,
                chat_id=chat_id,
                signals=signals
            )
            if result.get("success"):
                return result.get("message", "Studio signals activated")
            else:
                return f"Error: {result.get('message', 'Unknown error')}"

        elif knowledge_base_service.can_handle(tool_name):
            # Route to knowledge base service (Jira, Notion, GitHub, etc.)
            return knowledge_base_service.execute(
                project_id=project_id,
                chat_id=chat_id,
                tool_name=tool_name,
                tool_input=tool_input
            )

        elif mcp_registry and mcp_tool_service.can_handle(tool_name):
            # Route to MCP tool service (Freshdesk, GitHub MCP, etc.)
            return mcp_tool_service.execute(
                tool_name=tool_name,
                tool_input=tool_input,
                registry=mcp_registry,
            )

        else:
            return f"Unknown tool: {tool_name}"

    def _resolve_user_id(self, user_id: Optional[str] = None) -> str:
        """Resolve the active user for chat execution."""
        if user_id:
            return user_id
        identity = get_request_identity() if has_request_context() else None
        return identity.user_id if identity else DEFAULT_USER_ID

    def _emit_event(
        self,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]],
        event_name: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a structured event if a callback is registered."""
        if on_event:
            on_event(event_name, payload or {})

    def _build_sync_payload(
        self,
        project_id: str,
        chat_id: str,
        user_id: Optional[str],
    ) -> Dict[str, Any]:
        sync = chat_service.get_chat_sync_state(project_id, chat_id) or {}
        if user_id:
            try:
                sync["user_usage"] = get_user_service().get_usage_summary(user_id)
            except Exception as exc:
                logger.warning("Failed to build usage summary for %s: %s", user_id, exc)
                sync["user_usage"] = None
        else:
            sync["user_usage"] = None
        return sync

    def _call_claude(
        self,
        *,
        stream_text: bool,
        on_text_delta: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Call Claude once, optionally streaming text deltas.

        Returns:
            Tuple of (response_dict, full_text_for_this_response)
        """
        if not stream_text:
            response = claude_service.send_message(**kwargs)
            return response, claude_parsing_utils.extract_text(response)

        streamed_parts: List[str] = []

        def handle_delta(delta: str) -> None:
            streamed_parts.append(delta)
            if on_text_delta:
                on_text_delta(delta)

        try:
            response = claude_service.stream_message(
                on_text_delta=handle_delta,
                **kwargs,
            )
        except Exception as exc:
            partial_text = "".join(streamed_parts)
            raise ClaudeStreamError(str(exc), partial_text) from exc

        return response, "".join(streamed_parts)

    def _run_message_flow(
        self,
        project_id: str,
        chat_id: str,
        user_message_text: UserMessagePayload,
        *,
        stream_text: bool = False,
        user_id: Optional[str] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        cancel_event: Optional["object"] = None,
    ) -> Dict[str, Any]:
        """
        Shared chat runner for both non-streaming and streaming flows.
        """
        resolved_user_id = self._resolve_user_id(user_id)

        # Verify chat exists
        chat = chat_service.get_chat(project_id, chat_id)
        if not chat:
            raise ValueError("Chat not found")

        # Step 1: Store user message
        user_msg = message_service.add_user_message(project_id, chat_id, user_message_text)
        self._emit_event(on_event, "user_message", user_msg)

        # Step 2: Get config and build system prompt
        # Per-chat source selection: read which sources this chat has selected
        # None = legacy chat (never set) → fall back to all ready sources
        # [] = explicitly no sources selected
        selected_source_ids = chat.get("selected_source_ids")
        prompt_config = prompt_loader.get_project_prompt_config(project_id)
        base_prompt = prompt_config.get("system_prompt", "")
        system_prompt = self._build_system_prompt(
            project_id, base_prompt, user_id=resolved_user_id, selected_source_ids=selected_source_ids
        )

        # Step 3: Get tools (memory always available, search for non-CSV, analyzer for CSV)
        active_sources = context_loader.get_active_sources(project_id, selected_source_ids=selected_source_ids)
        # Separate sources by file extension (stored inside embedding_info)
        def _file_ext(source: Dict[str, Any]) -> str:
            embedding_info = source.get("embedding_info", {}) or {}
            return (embedding_info.get("file_extension") or "").lower()

        csv_sources = [s for s in active_sources if _file_ext(s) == ".csv"]
        database_sources = [s for s in active_sources if _file_ext(s) == ".database"]
        freshdesk_sources = [s for s in active_sources if _file_ext(s) == ".freshdesk"]
        jira_sources = [s for s in active_sources if _file_ext(s) == ".jira"]
        mixpanel_sources = [s for s in active_sources if _file_ext(s) == ".mixpanel"]
        non_csv_sources = [
            s for s in active_sources
            if _file_ext(s) not in (".csv", ".database", ".freshdesk", ".jira", ".mixpanel")
        ]
        tools, mcp_registry = self._get_tools(
            has_active_sources=bool(non_csv_sources),
            has_csv_sources=bool(csv_sources),
            has_database_sources=bool(database_sources),
            has_freshdesk_sources=bool(freshdesk_sources),
            has_jira_sources=bool(jira_sources),
            has_mixpanel_sources=bool(mixpanel_sources),
            user_id=resolved_user_id,
        )

        accumulated_text_parts: List[str] = []

        try:
            # Step 4: Build messages and call Claude
            api_messages = message_service.build_api_messages(project_id, chat_id)
            self._emit_event(on_event, "ping")

            response, response_text = self._call_claude(
                stream_text=stream_text,
                on_text_delta=on_text_delta,
                messages=api_messages,
                system_prompt=system_prompt,
                model=prompt_config.get("model"),
                max_tokens=prompt_config.get("max_tokens"),
                temperature=prompt_config.get("temperature"),
                tools=tools,
                project_id=project_id,
                user_id=resolved_user_id,
                chat_id=chat_id,
                tags=["chat"],
                # Opt the chat hot path into Anthropic prompt caching. The
                # system prompt + tools array are stable within a chat
                # session; cache hits are billed at 0.1× the input rate.
                enable_prompt_cache=True,
            )
            if response_text.strip():
                accumulated_text_parts.append(response_text)

            # Step 5: Handle tool use loop
            # Educational Note: When Claude wants to use tools, stop_reason is "tool_use".
            # We must execute tools and send back tool_result for each tool_use block.
            # Important: Claude can respond with text + tool_use together. The text is
            # the response to the user, the tool_use is for background processing.
            # We accumulate text from all responses so we don't lose it.
            iteration = 0
            # Track the most recent non-empty tool-result batch so we can
            # surface it to the user if the synthesis fallback also fails
            # to coax text out of Claude — sub-agent output is way more
            # useful than the "I've processed your request." placeholder.
            last_tool_results: List[Dict[str, Any]] = []

            while claude_parsing_utils.is_tool_use(response) and iteration < self.MAX_TOOL_ITERATIONS:
                iteration += 1

                # Bail out of the agent loop if the SSE client disconnected
                # (user clicked Stop). Skips further tool executions and the
                # final persist so we don't write a half-baked assistant
                # message — that was the "2 responses on resend" bug.
                if cancel_event is not None and cancel_event.is_set():
                    break

                # Get tool_use blocks from response (can be multiple for parallel tool calls)
                tool_use_blocks = claude_parsing_utils.extract_tool_use_blocks(response)

                if not tool_use_blocks:
                    break

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

                # Execute each tool and collect results, then persist them
                # all in ONE user message at the end of the round.
                #
                # Critical: Claude API requires every matching tool_result
                # for a single assistant tool_use round to live in ONE user
                # message. Splitting them across multiple consecutive user
                # rows produces a 400:
                #   "messages.N.content.0: unexpected tool_use_id found in
                #    tool_result blocks ... Each tool_result block must have
                #    a corresponding tool_use block in the previous message."
                # because the SECOND tool_result message's "previous message"
                # is the FIRST tool_result message (not the assistant
                # tool_use message), so Claude can't find the matching
                # tool_use.
                #
                # Educational Note: We wrap each tool execution in try/except
                # so a tool_result is ALWAYS produced. Without this, if a tool
                # throws, the assistant's tool_use block is orphaned (no
                # matching tool_result), which corrupts the message history
                # and 400s on every future message.
                tool_results_for_persist: List[Dict[str, Any]] = []
                for tool_block in tool_use_blocks:
                    tool_id = tool_block.get("id")
                    tool_name = tool_block.get("name")
                    tool_input = tool_block.get("input", {})

                    try:
                        result = self._execute_tool(
                            project_id,
                            chat_id,
                            tool_name,
                            tool_input,
                            user_id=resolved_user_id,
                            mcp_registry=mcp_registry,
                            user_message_text=user_message_text,
                            on_event=on_event,
                        )
                        is_error = False
                    except Exception as tool_error:
                        logger.error(f"Tool execution failed for {tool_name}: {tool_error}")
                        result = f"Tool execution failed: {str(tool_error)}"
                        is_error = True

                    tool_results_for_persist.append({
                        "tool_use_id": tool_id,
                        "result": result,
                        "is_error": is_error,
                    })

                # One DB row containing every tool_result, in the same
                # order as the assistant tool_use blocks above. This is the
                # message Claude API expects to be the "previous message"
                # when it next produces text or another tool_use round.
                if tool_results_for_persist:
                    message_service.add_tool_results_batch(
                        project_id=project_id,
                        chat_id=chat_id,
                        tool_results=tool_results_for_persist,
                    )
                    last_tool_results = tool_results_for_persist

                # All tool_results are now persisted (so the message chain
                # stays valid: every tool_use has a matching tool_result).
                # Bail BEFORE the next Claude call if the user clicked Stop —
                # otherwise we burn a full Claude API call whose response
                # we'd just throw away. The chain is already balanced, so
                # the next user message will work without a 400.
                if cancel_event is not None and cancel_event.is_set():
                    break

                # Rebuild messages and call Claude again
                api_messages = message_service.build_api_messages(project_id, chat_id)
                self._emit_event(on_event, "ping")

                response, response_text = self._call_claude(
                    stream_text=stream_text,
                    on_text_delta=on_text_delta,
                    messages=api_messages,
                    system_prompt=system_prompt,
                    model=prompt_config.get("model"),
                    max_tokens=prompt_config.get("max_tokens"),
                    temperature=prompt_config.get("temperature"),
                    tools=tools,
                    project_id=project_id,
                    user_id=resolved_user_id,
                    chat_id=chat_id,
                    tags=["chat"],
                    enable_prompt_cache=True,
                )
                if response_text.strip():
                    accumulated_text_parts.append(response_text)

            # Step 6: Store final text response
            # Educational Note: When Claude sends text + tool_use, the text comes first.
            # After tool execution, Claude may respond with more text OR empty (nothing to add).
            # We combine all text parts to show the complete response to the user.
            cancelled = cancel_event is not None and cancel_event.is_set()

            # If the agent loop ended without any narrated text — either
            # because we hit MAX_TOOL_ITERATIONS while still in tool_use,
            # or because Claude end_turned without emitting anything after
            # a tool round — force one more call WITHOUT tools so the
            # model can only produce prose. Prevents the
            # "I've processed your request." placeholder from showing up
            # while sub-agents produced rich tool_results that the user
            # paid for but never sees. Sub-agents already persisted their
            # tool_results via add_tool_results_batch, so build_api_messages
            # gives the synthesis call the full context.
            if not cancelled and not accumulated_text_parts:
                logger.warning(
                    "chat %s/%s: tool loop ended with no text "
                    "(stop_reason=%s, iterations=%d) — forcing tool-less synthesis call",
                    project_id, chat_id, response.get("stop_reason"), iteration,
                )
                try:
                    synthesis_messages = message_service.build_api_messages(project_id, chat_id)
                    synthesis_response, synthesis_text = self._call_claude(
                        stream_text=stream_text,
                        on_text_delta=on_text_delta,
                        messages=synthesis_messages,
                        system_prompt=system_prompt,
                        model=prompt_config.get("model"),
                        max_tokens=prompt_config.get("max_tokens"),
                        temperature=prompt_config.get("temperature"),
                        tools=None,
                        project_id=project_id,
                        user_id=resolved_user_id,
                        chat_id=chat_id,
                        tags=["chat", "synthesis_fallback"],
                        enable_prompt_cache=False,
                    )
                    if synthesis_text.strip():
                        accumulated_text_parts.append(synthesis_text)
                        # Use the synthesis call's usage/model when persisting
                        # below so the assistant message reflects the call
                        # that actually produced the visible text.
                        response = synthesis_response
                except Exception as synthesis_err:
                    logger.warning(
                        "synthesis fallback failed for chat %s/%s: %s",
                        project_id, chat_id, synthesis_err,
                    )

                # Last-resort: if Claude STILL didn't produce any text,
                # surface the sub-agents' raw output so the user sees
                # what their tokens actually paid for instead of the
                # bare placeholder. Filter to non-error results with
                # string content (e.g. the freshdesk / db / csv
                # analyzers all return formatted Markdown content).
                if not accumulated_text_parts and last_tool_results:
                    surfaced: List[str] = []
                    for tr in last_tool_results:
                        if tr.get("is_error"):
                            continue
                        raw = tr.get("result")
                        if isinstance(raw, str) and raw.strip():
                            surfaced.append(raw.strip())
                    if surfaced:
                        accumulated_text_parts.append(
                            "Here's what the analysis tools returned — I "
                            "wasn't able to wrap it into a final summary, "
                            "so ask a follow-up if you'd like me to dig in:\n\n"
                            + "\n\n---\n\n".join(surfaced)
                        )

            final_text = "\n\n".join(accumulated_text_parts) if accumulated_text_parts else ""

            # If the user clicked Stop while we were generating, persist a
            # stub assistant message marked as interrupted instead of the
            # full response. The chat history then reads as
            # "question → (stopped) → next question → answer", which is the
            # intuitive narrative for the user. Without this guard the
            # half-finished stream still landed in DB and showed up alongside
            # the user's revised answer (the "2 responses" symptom).

            if cancelled:
                stopped_content = (
                    final_text + "\n\n_(stopped by user)_"
                    if final_text.strip()
                    else "_(stopped by user)_"
                )
                assistant_msg = message_service.add_assistant_message(
                    project_id=project_id,
                    chat_id=chat_id,
                    content=stopped_content,
                    model=response.get("model"),
                    tokens=response.get("usage"),
                )
                # No on_event emit — the SSE generator is already closed.
            else:
                assistant_msg = message_service.add_assistant_message(
                    project_id=project_id,
                    chat_id=chat_id,
                    content=final_text if final_text.strip() else "I've processed your request.",
                    model=response.get("model"),
                    tokens=response.get("usage")
                )
                sync_payload = self._build_sync_payload(project_id, chat_id, resolved_user_id)
                self._emit_event(on_event, "assistant_done", {
                    "assistant_message": assistant_msg,
                    "sync": sync_payload,
                })

        except Exception as api_error:
            partial_text = api_error.partial_text if isinstance(api_error, ClaudeStreamError) else ""
            if partial_text.strip():
                accumulated_text_parts.append(partial_text)
            error_prefix = "\n\n".join(part for part in accumulated_text_parts if part.strip())

            # Provide a human-readable message for known API error types.
            error_str = str(api_error)
            if "overloaded_error" in error_str or "overloaded" in error_str.lower():
                friendly_error = "Overloaded error is on Anthropic's (Claude's) end, not NoobBook. Please try again in a moment."
            elif "rate_limit" in error_str:
                friendly_error = "Rate limit reached. Please wait a moment and try again."
            elif "assistant message prefill" in error_str or "must end with a user message" in error_str:
                friendly_error = "Something went wrong with the message sequence. Please try sending your message again."
            elif "tool_use_id" in error_str or "tool_result" in error_str:
                # Chain corruption — the persisted messages don't form a
                # valid tool_use/tool_result alternation. Show the user
                # an actionable path forward (start a fresh chat) and
                # dump the role/content-shape of every message in the
                # current chain so we can post-mortem from the log alone.
                friendly_error = (
                    "This chat's tool history got into a bad state. "
                    "Start a new chat to continue — your sources stay attached."
                )
                try:
                    chain_dump = [
                        {
                            "role": m.get("role"),
                            "content_type": (
                                "list" if isinstance(m.get("content"), list)
                                else "dict" if isinstance(m.get("content"), dict)
                                else "str"
                            ),
                            "block_types": (
                                [b.get("type") for b in m["content"] if isinstance(b, dict)]
                                if isinstance(m.get("content"), list) else None
                            ),
                            "tool_use_ids": (
                                [b.get("id") for b in m["content"]
                                 if isinstance(b, dict) and b.get("type") == "tool_use"]
                                if isinstance(m.get("content"), list) else None
                            ),
                            "tool_result_ids": (
                                [b.get("tool_use_id") for b in m["content"]
                                 if isinstance(b, dict) and b.get("type") == "tool_result"]
                                if isinstance(m.get("content"), list) else None
                            ),
                        }
                        for m in message_service.get_messages(project_id, chat_id)
                    ]
                    logger.error(
                        "Chat %s tool-chain corruption — API error: %s — chain shape: %s",
                        chat_id, error_str, chain_dump,
                    )
                except Exception as dump_exc:
                    logger.error(
                        "Chat %s tool-chain corruption — API error: %s — chain dump failed: %s",
                        chat_id, error_str, dump_exc,
                    )
            else:
                friendly_error = f"Sorry, I encountered an error: {error_str}"

            if error_prefix:
                error_content = f"{error_prefix}\n\n{friendly_error}"
            else:
                error_content = friendly_error
            # Store error message
            assistant_msg = message_service.add_assistant_message(
                project_id=project_id,
                chat_id=chat_id,
                content=error_content,
                error=True
            )
            self._emit_event(
                on_event,
                "error",
                {
                    "message": str(api_error),
                    "assistant_message": assistant_msg,
                    "sync": self._build_sync_payload(project_id, chat_id, resolved_user_id),
                },
            )

        # Step 7: Sync chat index
        chat_service.sync_chat_to_index(project_id, chat_id)

        # Step 8: Auto-rename chat on first message (background task)
        # Educational Note: We check if the chat had no messages before this one.
        # The naming runs in background so it doesn't block the response.
        if chat.get("message_count", 0) == 0:
            # Submit naming task to background
            # Chat naming uses the plain-text portion only — image-block
            # metadata isn't useful for picking a 1-5 word title.
            task_service.submit_task(
                "chat_naming",
                chat_id,
                self._generate_and_update_chat_title,
                project_id,
                chat_id,
                _extract_user_text(user_message_text),
                target_type="chat",
            )

        return {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "sync": self._build_sync_payload(project_id, chat_id, resolved_user_id),
        }

    def send_message(
        self,
        project_id: str,
        chat_id: str,
        user_message_text: UserMessagePayload,
    ) -> Dict[str, Any]:
        """Process a user message and return saved messages plus sync metadata."""
        return self._run_message_flow(
            project_id=project_id,
            chat_id=chat_id,
            user_message_text=user_message_text,
            stream_text=False,
        )

    def stream_message(
        self,
        project_id: str,
        chat_id: str,
        user_message_text: UserMessagePayload,
        *,
        user_id: Optional[str] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        cancel_event: Optional["object"] = None,
    ) -> Dict[str, Any]:
        """Process a user message while streaming assistant text deltas."""
        return self._run_message_flow(
            project_id=project_id,
            chat_id=chat_id,
            user_message_text=user_message_text,
            stream_text=True,
            user_id=user_id,
            on_text_delta=lambda delta: self._emit_event(
                on_event,
                "assistant_delta",
                {"delta": delta},
            ),
            on_event=on_event,
            cancel_event=cancel_event,
        )

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
        except Exception as e:
            logger.error("Failed to auto-name chat %s: %s", chat_id, e)


# Singleton instance
main_chat_service = MainChatService()
