"""
Deep Research Agent - AI agent for comprehensive topic research.

Educational Note: This is an agentic loop that researches a topic by:
1. Searching the web using web_search (server) and tavily_search_advance (client)
2. Writing research segments incrementally to a file
3. Terminating when is_last_segment=true in write_research_to_file

Tool execution is delegated to deep_research_executor following the
standard separation of concerns pattern.
"""

import logging
import uuid
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.services.tool_executors import deep_research_executor
from app.services.data_services import message_service
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class DeepResearchAgent:
    """
    Deep research agent for comprehensive topic exploration.

    Educational Note: Uses incremental file writing pattern:
    - Agent searches for information using web_search + tavily_search_advance
    - Agent writes research in segments using write_research_to_file
    - Each segment is appended to the output file
    - Agent terminates when is_last_segment=true
    """

    AGENT_NAME = "deep_research"
    MAX_ITERATIONS = 40

    def __init__(self):
        """Initialize agent with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("deep_research_agent")
        return self._prompt_config

    def _load_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load agent tools from deep_research category."""
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    def research(
        self,
        project_id: str,
        source_id: str,
        topic: str,
        description: str,
        links: List[str] = None,
        output_path: str = ""
    ) -> Dict[str, Any]:
        """
        Run comprehensive research on a topic.

        Educational Note: The research loop:
        1. Agent searches web for information
        2. Agent writes segments to file incrementally
        3. write_research_to_file with is_last_segment=true ends the loop

        Args:
            project_id: The project UUID
            source_id: The source UUID
            topic: The main research topic
            description: Focus areas and questions to answer
            links: Optional list of reference URLs to analyze
            output_path: Path to write research output (required, must be non-empty)

        Returns:
            Dict with success status and research metadata
        """
        if not output_path:
            raise ValueError("output_path is required")

        config = self._load_config()
        tools_config = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()
        links = links or []

        # Build user message from template
        links_context = "\n".join([f"- {link}" for link in links]) if links else "No specific links provided."
        user_message = config.get("user_message_template", "Research this topic: {topic}").format(
            topic=topic,
            description=description,
            links_context=links_context
        )

        # Initialize messages
        messages = [{"role": "user", "content": user_message}]

        # Get tools
        all_tools = tools_config["all_tools"]

        total_input_tokens = 0
        total_output_tokens = 0
        segments_written = 0

        logger.info("Starting deep research on: %s (id: %s)", topic, execution_id[:8])

        for iteration in range(1, self.MAX_ITERATIONS + 1):

            # Call Claude API
            response = claude_service.send_message(
                messages=messages,
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=all_tools,
                tool_choice={"type": "any"},
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

            # Process tool calls via executor
            tool_results = []
            research_complete = False

            for block in content_blocks:
                block_type = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")

                if block_type == "tool_use":
                    tool_name = getattr(block, "name", "") if hasattr(block, "name") else block.get("name", "")
                    tool_input = getattr(block, "input", {}) if hasattr(block, "input") else block.get("input", {})
                    tool_id = getattr(block, "id", "") if hasattr(block, "id") else block.get("id", "")

                    # Track segments for write tool
                    if tool_name == "write_research_to_file":
                        segments_written += 1

                    # Execute via executor
                    result_message, is_termination = deep_research_executor.execute_tool(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        output_path=output_path
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_message
                    })

                    if is_termination:
                        research_complete = True

                elif block_type == "server_tool_use":
                    # Server tools (web_search) - Claude handles execution
                    pass

            # Add tool results to messages if any
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Check if research is complete
            if research_complete:
                logger.info("Research completed in %d iterations", iteration)
                final_result = {
                    "success": True,
                    "output_path": output_path,
                    "segments_written": segments_written,
                    "iterations": iteration,
                    "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
                    "completed_at": datetime.now().isoformat()
                }
                self._save_execution(
                    project_id, execution_id, topic, messages, final_result, started_at, source_id
                )
                return final_result

        # Max iterations reached
        logger.warning("Max iterations reached (%d)", self.MAX_ITERATIONS)
        error_result = {
            "success": False,
            "output_path": output_path,
            "segments_written": segments_written,
            "error": f"Research reached maximum iterations ({self.MAX_ITERATIONS})",
            "iterations": self.MAX_ITERATIONS,
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
        }
        self._save_execution(
            project_id, execution_id, topic, messages, error_result, started_at, source_id
        )
        return error_result

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        topic: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: str
    ) -> None:
        """Save execution log for debugging."""
        if not project_id:
            return

        try:
            log_data = {
                "execution_id": execution_id,
                "agent": self.AGENT_NAME,
                "topic": topic,
                "source_id": source_id,
                "started_at": started_at,
                "completed_at": datetime.now().isoformat(),
                "result": result,
                "message_count": len(messages)
            }

            message_service.save_agent_log(
                project_id=project_id,
                agent_name=self.AGENT_NAME,
                execution_id=execution_id,
                log_data={**log_data, "messages": messages}
            )
        except Exception as e:
            logger.exception("Error saving execution log")


# Singleton instance
deep_research_agent = DeepResearchAgent()
