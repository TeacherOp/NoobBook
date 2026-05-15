"""
CSV Analyzer Agent - AI agent for answering questions about CSV data.

Educational Note: This agent uses pandas for flexible data analysis:
1. Receives a user query about a CSV file
2. Writes and executes pandas code via run_analysis tool
3. Can generate visualizations with matplotlib/seaborn
4. Returns final answer via return_analysis (termination tool)

The agent is triggered by main_chat when user asks about CSV sources.
Results (including any generated plots) are returned to main_chat.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.services.tool_executors.analysis_executor import analysis_executor
from app.services.data_services import message_service
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class CSVAnalyzerAgent:
    """
    Agent for answering user questions about CSV data using pandas.

    Educational Note: This agent writes pandas code dynamically,
    enabling flexible analysis for any question about the data.
    """

    AGENT_NAME = "csv_analyzer_agent"
    MAX_ITERATIONS = 40
    TERMINATION_TOOL = "return_analysis"

    def __init__(self):
        """Initialize agent with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("csv_analyzer_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        """
        Load tools for data analysis.

        Educational Note: We load tools from analysis_agent category:
        - run_analysis: Execute pandas code
        - return_analysis: Return final answer with optional plots
        """
        if self._tools is None:
            tools_config = tool_loader.load_tools_for_agent("analysis_agent")
            self._tools = tools_config["all_tools"]
        return self._tools

    def run(
        self,
        project_id: str,
        source_id: str,
        query: str,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent to answer a question about CSV data.

        Educational Note: The agent writes pandas code to answer questions.
        It can run multiple queries and generate plots before returning.

        Args:
            project_id: Project ID (for file paths and cost tracking)
            source_id: Source ID of the CSV file
            query: User's question about the data

        Returns:
            Dict with success status, summary, and optional image_paths
        """
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Build user message with query
        user_message = config.get("user_message", "Analyze this data.").format(
            filename=f"{source_id}.csv",
            query=query
        )

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0

        # Track generated plot paths across iterations
        generated_plots = []

        logger.info("Starting CSV analysis for: %s", query[:50])

        for iteration in range(1, self.MAX_ITERATIONS + 1):

            response = claude_service.send_message(
                messages=messages,
                system_prompt=config.get("system_prompt", ""),
                model=config.get("model"),
                max_tokens=config.get("max_tokens"),
                temperature=config.get("temperature"),
                tools=tools,
                tool_choice={"type": "any"},
                project_id=project_id,
                tags=["query"],
                chat_id=chat_id,
                user_id=user_id,
                enable_prompt_cache=True,
            )

            total_input_tokens += response["usage"]["input_tokens"]
            total_output_tokens += response["usage"]["output_tokens"]

            content_blocks = response.get("content_blocks", [])
            tool_blocks = claude_parsing_utils.extract_tool_use_blocks(response)

            # Check for tool blocks BEFORE appending to messages.
            # Appending first then doing `continue` would leave messages ending
            # with an assistant role, causing a prefill API error on the next iteration.
            if not tool_blocks:
                # Claude ended the turn without calling return_analysis.
                # Previously this just `continue`d, which guaranteed we
                # burned every remaining iteration on the same dead path
                # (and contributed to the 27 "Max iterations reached (20)"
                # warnings in prod). Accept the text answer instead.
                if claude_parsing_utils.is_end_turn(response):
                    text = claude_parsing_utils.extract_text(response).strip()
                    if text:
                        logger.info(
                            "CSV analyzer ended on text response (iter %d, no termination tool)",
                            iteration,
                        )
                        # Append the final assistant content to messages
                        # BEFORE save_execution so the saved transcript
                        # ends with the answer that was actually returned
                        # to the user. The "defer-append" pattern at the
                        # top of this block is to keep messages ending
                        # with a user role when we `continue` — but this
                        # is a terminal `return`, so appending here is
                        # both safe and necessary.
                        serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
                        messages.append({"role": "assistant", "content": serialized_content})
                        final_result = self._build_result(
                            {
                                "summary": text,
                                "image_paths": generated_plots,
                            },
                            iteration,
                            total_input_tokens,
                            total_output_tokens,
                        )
                        self._save_execution(
                            project_id, execution_id, query, messages,
                            final_result, started_at, source_id,
                        )
                        return final_result
                    logger.warning("End turn with no text and no tool — bailing")
                    break
                continue

            serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
            messages.append({"role": "assistant", "content": serialized_content})

            tool_results_data = []

            for tool_block in tool_blocks:
                tool_name = tool_block["name"]
                tool_input = tool_block["input"]
                tool_id = tool_block["id"]

                # Execute tool via analysis_executor
                result, is_termination = analysis_executor.execute_tool(
                    tool_name, tool_input, project_id, source_id
                )

                if is_termination:
                    logger.info("Completed in %d iterations", iteration)

                    # Add any plots generated during this session
                    if generated_plots:
                        result["image_paths"] = generated_plots

                    final_result = self._build_result(
                        result,
                        iteration,
                        total_input_tokens,
                        total_output_tokens
                    )

                    self._save_execution(
                        project_id, execution_id, query, messages,
                        final_result, started_at, source_id
                    )
                    return final_result

                # Track any plot filenames from run_analysis
                if result.get("plot_filenames"):
                    generated_plots.extend(result["plot_filenames"])

                # Format result for Claude
                content = self._format_tool_result(result)
                tool_results_data.append({
                    "tool_use_id": tool_id,
                    "result": content
                })

            if tool_results_data:
                tool_results_content = claude_parsing_utils.build_tool_result_content(tool_results_data)
                messages.append({"role": "user", "content": tool_results_content})

        logger.warning("Max iterations reached (%d) — forcing tool-less synthesis", self.MAX_ITERATIONS)

        # Same shape as the main-chat synthesis fallback (commit c60393a):
        # the loop has expensive context — run_analysis tool results,
        # generated plots, partial reasoning — that the user paid for.
        # Force one more Claude call with tools=None so the model can
        # only emit prose, and surface that as the answer. Falls through
        # to the original error_result only if even this call fails.
        try:
            synthesis_response = claude_service.send_message(
                messages=messages,
                system_prompt=config.get("system_prompt", ""),
                model=config.get("model"),
                max_tokens=config.get("max_tokens"),
                temperature=config.get("temperature"),
                tools=None,
                project_id=project_id,
                tags=["query", "synthesis_fallback"],
                chat_id=chat_id,
                user_id=user_id,
            )
            synthesis_usage = synthesis_response.get("usage", {})
            total_input_tokens += synthesis_usage.get("input_tokens", 0)
            total_output_tokens += synthesis_usage.get("output_tokens", 0)
            synthesis_text = claude_parsing_utils.extract_text(synthesis_response).strip()
            if synthesis_text:
                # Append the synthesis assistant content to messages
                # BEFORE _save_execution so the saved transcript ends
                # with the answer the user actually saw — same shape as
                # the end-turn-text branch above. The synthesis call ran
                # with tools=None, so its content_blocks are pure text.
                synthesis_blocks = synthesis_response.get("content_blocks", [])
                synthesis_serialized = claude_parsing_utils.serialize_content_blocks(synthesis_blocks)
                messages.append({"role": "assistant", "content": synthesis_serialized})
                final_result = self._build_result(
                    {"summary": synthesis_text, "image_paths": generated_plots},
                    self.MAX_ITERATIONS,
                    total_input_tokens,
                    total_output_tokens,
                )
                self._save_execution(
                    project_id, execution_id, query, messages,
                    final_result, started_at, source_id,
                )
                return final_result
        except Exception as exc:
            logger.warning("CSV analyzer synthesis fallback failed: %s", exc)

        error_result = {
            "success": False,
            "error": f"Analysis did not complete within {self.MAX_ITERATIONS} iterations",
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
        }

        self._save_execution(
            project_id, execution_id, query, messages,
            error_result, started_at, source_id
        )
        return error_result

    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        """Format tool result for Claude."""
        if not result.get("success"):
            return f"Error: {result.get('error', 'Unknown error')}"

        return result.get("output", "Code executed successfully")

    def _build_result(
        self,
        tool_input: Dict[str, Any],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """
        Build the final result from return_analysis tool input.

        Educational Note: The termination tool input contains:
        - summary: Text answer to the user's question
        - data: Optional structured data
        - image_paths: Paths to generated plots
        """
        return {
            "success": True,
            "summary": tool_input.get("summary", ""),
            "data": tool_input.get("data"),
            "image_paths": tool_input.get("image_paths", []),
            "iterations": iterations,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "generated_at": datetime.now().isoformat()
        }

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        query: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: str
    ) -> None:
        """Save execution log for debugging."""
        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Analyze CSV: {query}",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "query": query}
        )


csv_analyzer_agent = CSVAnalyzerAgent()
