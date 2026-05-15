"""
Web Agent Service - AI agent for web content extraction and search.

Educational Note: This is a simple agentic loop pattern:
1. Send task to Claude with tools (2 server tools + 2 client tools)
2. Loop until 'return_search_result' tool is called
3. Server tools (web_fetch, web_search) - Claude handles execution
4. Client tools (tavily_search) - we execute and send result back
5. Termination tool (return_search_result) - extract input as final result

Tools:
- web_fetch: Server tool - fetches URL content (Claude handles)
- web_search: Server tool - searches web (Claude handles)
- tavily_search: Client tool - Tavily AI search (we execute)
- return_search_result: Termination tool - signals completion
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.services.tool_executors import web_agent_executor
from app.services.data_services import message_service
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class WebAgentService:
    """
    Simple web content extraction agent.

    Educational Note: Agent loops are simpler than they seem:
    - Keep calling Claude until a specific tool signals completion
    - Server tools require no action from us
    - Client tools need execution and result sent back
    """

    AGENT_NAME = "web_agent"
    MAX_ITERATIONS = 40

    def __init__(self):
        """Initialize agent with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("web_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        """
        Load all 4 agent tools.

        Educational Note: We load tools from JSON files:
        - 2 server tools (web_fetch, web_search) - type: "server_tool"
        - 1 client tool (tavily_search) - we execute
        - 1 termination tool (return_search_result) - signals completion
        """
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    # =========================================================================
    # Agent Loop - Simple and Clean
    # =========================================================================

    def run(
        self,
        url: str,
        project_id: Optional[str] = None,
        source_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the agent to extract content from a URL.

        Educational Note: Simple agentic loop:
        1. URL is injected into system_prompt
        2. user_message from config triggers the agent
        3. Loop until return_search_result tool is called
        4. Server tools (web_fetch, web_search) - Claude handles
        5. Client tools (tavily_search) - we execute
        """
        config = self._load_config()
        tools_config = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Inject URL into system prompt
        system_prompt = config["system_prompt"] + f"\n\nURL to extract: {url}"

        # Get all tools and beta headers for server tools
        all_tools = tools_config["all_tools"]
        beta_headers = tools_config.get("beta_headers", [])
        valid_beta_headers = [h for h in beta_headers if h is not None]
        extra_headers = {"anthropic-beta": ",".join(valid_beta_headers)} if valid_beta_headers else None

        # Initial message from config - triggers the agent
        user_message = config.get("user_message", "Please run the analysis.")
        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0

        logger.info("Starting web agent %s", execution_id[:8])

        for iteration in range(1, self.MAX_ITERATIONS + 1):

            # Call Claude API
            response = claude_service.send_message(
                messages=messages,
                system_prompt=system_prompt,
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=all_tools,
                tool_choice={"type": "any"},
                extra_headers=extra_headers,
                project_id=project_id,
                enable_prompt_cache=True,
            )

            # Track token usage
            total_input_tokens += response["usage"]["input_tokens"]
            total_output_tokens += response["usage"]["output_tokens"]

            # Serialize and add assistant response to messages
            content_blocks = response.get("content_blocks", [])
            serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
            messages.append({"role": "assistant", "content": serialized_content})

            # Process tool calls - simple inline logic
            tool_results = []

            for block in content_blocks:
                block_type = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")

                if block_type == "tool_use":
                    tool_name = getattr(block, "name", "") if hasattr(block, "name") else block.get("name", "")
                    tool_input = getattr(block, "input", {}) if hasattr(block, "input") else block.get("input", {})
                    tool_id = getattr(block, "id", "") if hasattr(block, "id") else block.get("id", "")

                    # TERMINATION: return_search_result means we're done
                    if tool_name == "return_search_result":
                        final_result = self._build_result(
                            tool_input, iteration, total_input_tokens, total_output_tokens
                        )
                        logger.info("Completed in %d iterations", iteration)

                        # Save execution log
                        self._save_execution(
                            project_id, execution_id, url, messages,
                            final_result, started_at, source_id
                        )
                        return final_result

                    # CLIENT TOOL: tavily_search - execute and add result
                    elif tool_name == "tavily_search":
                        result, _ = web_agent_executor.execute_tool(tool_name, tool_input)
                        # Result is already a formatted string, use directly
                        content = result if isinstance(result, str) else json.dumps(result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": content
                        })

                elif block_type == "server_tool_use":
                    # SERVER TOOLS: web_fetch, web_search - Claude handles, no action needed
                    pass

            # Add tool results to messages if any client tools were executed
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        # Max iterations reached
        logger.warning("Max iterations reached (%d)", self.MAX_ITERATIONS)
        error_result = {
            "success": False,
            "error_message": f"Agent reached maximum iterations ({self.MAX_ITERATIONS})",
            "iterations": self.MAX_ITERATIONS,
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
        }
        self._save_execution(
            project_id, execution_id, url, messages,
            error_result, started_at, source_id
        )
        return error_result

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_result(
        self,
        tool_input: Dict[str, Any],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """
        Build the final result from return_search_result tool input.

        Educational Note: The termination tool's input IS the result.
        We just add metadata (iterations, token usage, timestamp).
        """
        return {
            "success": tool_input.get("success", False),
            "title": tool_input.get("title", ""),
            "url": tool_input.get("url", ""),
            "content": tool_input.get("content", ""),
            "summary": tool_input.get("summary", ""),
            "content_type": tool_input.get("content_type", "other"),
            "source_urls": tool_input.get("source_urls", []),
            "error_message": tool_input.get("error_message"),
            "iterations": iterations,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "extracted_at": datetime.now().isoformat()
        }

    def _save_execution(
        self,
        project_id: Optional[str],
        execution_id: str,
        url: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: Optional[str] = None
    ) -> None:
        """Save execution log using message_service."""
        if not project_id:
            return

        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Extract content from: {url}",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "url": url}
        )


# Singleton instance
web_agent_service = WebAgentService()
