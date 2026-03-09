"""
Database Analyzer Agent - AI agent for answering questions using live DB data.

Educational Note: This agent is triggered by main chat via the analyze_database_agent tool.
It uses tool-calling to:
1) Inspect schema via schema_fetcher
2) Run read-only SQL via query_runner
3) Return a final answer via return_database_result (termination tool)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.services.data_services import message_service
from app.services.tool_executors.database_executor import DatabaseExecutor
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class DatabaseAnalyzerAgent:
    """
    Agent for answering questions about DATABASE sources (Postgres/MySQL) using SQL.
    """

    AGENT_NAME = "database_analyzer_agent"
    MAX_ITERATIONS = 20
    TERMINATION_TOOL = "return_database_result"

    def __init__(self) -> None:
        self._prompt_config: Dict[str, Any] | None = None
        self._tools: List[Dict[str, Any]] | None = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("database_analyzer_agent")
        return self._prompt_config or {}

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            tools_config = tool_loader.load_tools_for_agent("database_agent")
            self._tools = tools_config["all_tools"]
        return self._tools or []

    def run(self, project_id: str, source_id: str, query: str) -> Dict[str, Any]:
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Defensive defaults: prompt configs live in a writable volume in Docker,
        # so a missing/new prompt file shouldn't crash the agent.
        model = config.get("model") or "claude-sonnet-4-6"
        max_tokens = config.get("max_tokens")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            max_tokens = 4500
        temperature = config.get("temperature")
        if not isinstance(temperature, (int, float)):
            temperature = 0.0
        system_prompt = config.get("system_prompt") or ""

        user_message_template = config.get("user_message") or "Database source ID: {source_id}\n\nUser question: {query}"
        user_message = user_message_template.format(
            source_id=source_id,
            query=query,
        )

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0

        executed_queries: List[str] = []

        executor = DatabaseExecutor()

        # Pre-flight check: verify the database connection is resolvable
        # BEFORE entering the expensive agent loop. This prevents wasting
        # API calls when the connection is missing or inaccessible.
        try:
            resolved = executor.validate_connection(project_id, source_id)
            logger.info(
                "DB agent pre-flight OK: connection_id=%s, db_type=%s, source_id=%s",
                resolved.connection_id, resolved.db_type, source_id,
            )
        except Exception as e:
            logger.error(
                "DB agent pre-flight FAILED for source_id=%s: %s",
                source_id, e,
            )
            error_result = {
                "success": False,
                "error": (
                    f"Cannot connect to database: {e}. "
                    f"Please verify the connection in Settings → Databases is still active "
                    f"and accessible from the server."
                ),
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }
            self._save_execution(
                project_id=project_id,
                execution_id=execution_id,
                query=query,
                messages=messages,
                result=error_result,
                started_at=started_at,
                source_id=source_id,
            )
            return error_result

        # Track consecutive tool errors to bail out early instead of
        # burning through all MAX_ITERATIONS on repeated failures.
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 3

        try:
            for iteration in range(1, self.MAX_ITERATIONS + 1):
                response = claude_service.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                    tool_choice={"type": "any"},
                    extra_headers={"anthropic-beta": "context-1m-2025-08-07"},
                    project_id=project_id,
                )

                total_input_tokens += response["usage"]["input_tokens"]
                total_output_tokens += response["usage"]["output_tokens"]

                content_blocks = response.get("content_blocks", [])
                serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
                messages.append({"role": "assistant", "content": serialized_content})

                tool_blocks = claude_parsing_utils.extract_tool_use_blocks(response)
                if not tool_blocks:
                    continue

                tool_results_data = []
                iteration_had_error = False

                for tool_block in tool_blocks:
                    tool_name = tool_block.get("name")
                    tool_input = tool_block.get("input", {}) or {}
                    tool_id = tool_block.get("id")

                    result, is_termination = executor.execute_tool(
                        tool_name, tool_input, project_id, source_id
                    )

                    if tool_name == "query_runner" and isinstance(tool_input.get("query"), str):
                        executed_queries.append(tool_input["query"])

                    # Track errors for early bail-out
                    if isinstance(result, dict) and not result.get("success", True):
                        iteration_had_error = True

                    if is_termination:
                        # Ensure we preserve executed queries for debugging.
                        if isinstance(result, dict) and not result.get("sql_queries"):
                            result["sql_queries"] = executed_queries

                        final_result = self._build_result(
                            result,
                            iteration,
                            total_input_tokens,
                            total_output_tokens,
                        )

                        self._save_execution(
                            project_id=project_id,
                            execution_id=execution_id,
                            query=query,
                            messages=messages,
                            result=final_result,
                            started_at=started_at,
                            source_id=source_id,
                        )
                        return final_result

                    tool_results_data.append(
                        {
                            "tool_use_id": tool_id,
                            "result": self._format_tool_result(result),
                        }
                    )

                if tool_results_data:
                    tool_results_content = claude_parsing_utils.build_tool_result_content(tool_results_data)
                    messages.append({"role": "user", "content": tool_results_content})

                # Early bail-out: if we get the same type of error repeatedly,
                # stop wasting API calls and return immediately.
                if iteration_had_error:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.warning(
                            "DB agent: %d consecutive tool errors, bailing out early "
                            "(source_id=%s, iteration=%d)",
                            consecutive_errors, source_id, iteration,
                        )
                        error_result = {
                            "success": False,
                            "error": (
                                f"Database query failed after {consecutive_errors} consecutive errors. "
                                f"The database may be unreachable or the connection may have expired."
                            ),
                            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
                        }
                        self._save_execution(
                            project_id=project_id,
                            execution_id=execution_id,
                            query=query,
                            messages=messages,
                            result=error_result,
                            started_at=started_at,
                            source_id=source_id,
                        )
                        return error_result
                else:
                    consecutive_errors = 0

            error_result = {
                "success": False,
                "error": f"Analysis did not complete within {self.MAX_ITERATIONS} iterations",
                "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            }
            self._save_execution(
                project_id=project_id,
                execution_id=execution_id,
                query=query,
                messages=messages,
                result=error_result,
                started_at=started_at,
                source_id=source_id,
            )
            return error_result

        finally:
            executor.close_connections()

    @staticmethod
    def _format_tool_result(result: Dict[str, Any]) -> str:
        if not result.get("success"):
            return f"Error: {result.get('error', 'Unknown error')}"

        try:
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception:
            return str(result)

    @staticmethod
    def _build_result(
        termination_input: Dict[str, Any],
        iterations: int,
        input_tokens: int,
        output_tokens: int,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "summary": termination_input.get("summary", ""),
            "findings": termination_input.get("findings") or [],
            "sql_queries": termination_input.get("sql_queries") or [],
            "iterations": iterations,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "generated_at": datetime.now().isoformat(),
        }

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        query: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: str,
    ) -> None:
        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Analyze DB: {query}",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "query": query},
        )


database_analyzer_agent = DatabaseAnalyzerAgent()
