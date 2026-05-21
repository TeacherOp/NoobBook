"""
Freshdesk Analyzer Agent - Agentic loop for analyzing Freshdesk ticket data.

Educational Note: Follows the same pattern as database_analyzer_agent.py.
Claude iterates with tools (schema_info, query_runner) until it calls
return_ticket_analysis to terminate with structured output.
"""

import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from app.config import prompt_loader, tool_loader
from app.services.integrations.claude import claude_service
from app.utils import claude_parsing_utils
from app.services.tool_executors.freshdesk_executor import freshdesk_executor

logger = logging.getLogger(__name__)


class FreshdeskAnalyzerAgent:
    AGENT_NAME = "freshdesk_analyzer_agent"
    MAX_ITERATIONS = 40
    TERMINATION_TOOL = "return_ticket_analysis"

    def __init__(self):
        self._tools = None

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_from_category("freshdesk_agent")
        return self._tools

    @staticmethod
    def _emit_progress(
        on_event: Optional[Callable[[str, Dict[str, Any]], None]],
        message: str,
        *,
        iteration: Optional[int] = None,
        tool: Optional[str] = None,
    ) -> None:
        """Emit a ``tool_progress`` SSE event if a callback is wired up.
        Safe no-op when on_event is None (non-streaming send_message path).
        The payload shape mirrors the events main_chat_service already
        sends so the frontend handler can render them uniformly."""
        if on_event is None:
            return
        try:
            payload: Dict[str, Any] = {"agent": "freshdesk", "message": message}
            if iteration is not None:
                payload["iteration"] = iteration
            if tool is not None:
                payload["tool"] = tool
            on_event("tool_progress", payload)
        except Exception:
            # A failure in event emission must not abort the agent run.
            # The SSE queue may have a backpressure or the client may
            # have disconnected — the agent can still complete and the
            # full response will be persisted via main_chat_service.
            logger.debug("tool_progress emit failed", exc_info=True)

    def run(
        self,
        project_id: str,
        source_id: str,
        query: str,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Run the Freshdesk analysis agentic loop.
        Always closes the DB connection on exit to prevent leaks."""
        execution_id = str(uuid.uuid4())[:8]
        logger.info("[FreshdeskAgent:%s] Starting analysis for source %s", execution_id, source_id)
        self._emit_progress(on_event, "Connecting to Freshdesk tickets…")

        # Load config
        prompt_config = prompt_loader.get_prompt_config(self.AGENT_NAME)
        tools = self._load_tools()

        # Ground the agent in today's date so "yesterday", "last 7 days", etc.
        # map to concrete timestamp filters on ticket_created_at.
        from datetime import date
        today_line = f"Today's date: {date.today().isoformat()}"
        system_prompt = f"{today_line}\n\n{prompt_config.get('system_prompt', '')}"
        model = prompt_config.get("model", "claude-sonnet-4-6")
        max_tokens = prompt_config.get("max_tokens", 4096)
        temperature = prompt_config.get("temperature", 0.0)

        messages = [{"role": "user", "content": f"Freshdesk source ID: {source_id}\n\nUser question: {query}"}]

        total_usage = {"input_tokens": 0, "output_tokens": 0}
        all_queries: List[str] = []
        consecutive_errors = 0

        try:
            # Pre-flights inside the try so the finally still closes the DB
            # connection on early returns.
            #
            # `validate_connection` goes through the Supabase REST client
            # (same path the sync service uses), so a failure here means the
            # backend really can't reach the freshdesk_tickets table — not
            # that direct psycopg2 access is unconfigured.
            if not freshdesk_executor.validate_connection():
                return {
                    "success": False,
                    "error": (
                        "Couldn't reach the Freshdesk tickets table. "
                        "Verify the backend's Supabase credentials and that "
                        "the freshdesk_tickets migration has been applied."
                    ),
                }

            # Without this pre-flight the agent loop runs against an empty
            # table, every query returns zero rows, and the model paraphrases
            # that as "Freshdesk connection had an issue" — a vague message
            # that hides the real cause (sync hasn't run yet).
            schema_info = freshdesk_executor.get_schema_info()
            if not schema_info.get("success"):
                # Surface the underlying exception so the operator can act
                # on it (wrong DB url, missing column, RLS denial). The
                # generic "table is unavailable" alone isn't actionable.
                underlying = schema_info.get("error", "unknown error")
                return {
                    "success": False,
                    "error": (
                        f"Freshdesk tickets table is unavailable: {underlying}. "
                        "If the table is empty, open the Sources panel and "
                        "click 'Sync New' on the Freshdesk Tickets source."
                    ),
                }
            if not schema_info.get("ticket_count"):
                return {
                    "success": False,
                    "error": (
                        "No Freshdesk tickets have been synced yet. "
                        "Open the Sources panel and click 'Sync New' (or 'Re-sync All') "
                        "on the Freshdesk Tickets source, wait for the sync to finish, then ask again."
                    ),
                }

            for iteration in range(1, self.MAX_ITERATIONS + 1):
                iter_t0 = time.monotonic()
                logger.info(
                    "FRESHDESK_AGENT_ITER exec=%s iter=%d", execution_id, iteration
                )
                # Per-iteration heartbeat. Tells the user "still working" even
                # when the tool a given iteration runs is fast enough to not
                # produce its own progress event below. Without this the user
                # sees a 30-60s blank wait while Claude+SQL iterate silently.
                self._emit_progress(
                    on_event,
                    f"Analyzing tickets (step {iteration})…",
                    iteration=iteration,
                )

                response = claude_service.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                    project_id=project_id,
                    tags=["query"],
                    chat_id=chat_id,
                    user_id=user_id,
                    enable_prompt_cache=True,
                )

                # Track usage
                usage = response.get("usage", {})
                total_usage["input_tokens"] += usage.get("input_tokens", 0)
                total_usage["output_tokens"] += usage.get("output_tokens", 0)

                if claude_parsing_utils.is_end_turn(response):
                    text = claude_parsing_utils.extract_text(response)
                    return {
                        "success": True,
                        "content": text,
                        "summary": text,
                        "findings": [],
                        "recommendations": [],
                        "sql_queries": all_queries,
                        "iterations": iteration,
                        "usage": total_usage,
                    }

                if not claude_parsing_utils.is_tool_use(response):
                    text = claude_parsing_utils.extract_text(response)
                    return {"success": True, "content": text, "iterations": iteration, "usage": total_usage}

                # Process tool calls
                tool_blocks = claude_parsing_utils.extract_tool_use_blocks(response)
                content_blocks = response.get("content_blocks", [])
                messages.append({"role": "assistant", "content": content_blocks})

                tool_results = []
                terminated = False
                termination_result = None

                for block in tool_blocks:
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    tool_id = block.get("id", "")

                    # Emit a specific message per tool so the user sees
                    # what's actually happening (querying / summarizing /
                    # returning), not just generic "Analyzing…".
                    if tool_name == "query_runner":
                        self._emit_progress(
                            on_event,
                            "Running ticket query…",
                            iteration=iteration,
                            tool=tool_name,
                        )
                    elif tool_name == "schema_info":
                        self._emit_progress(
                            on_event,
                            "Reading ticket schema…",
                            iteration=iteration,
                            tool=tool_name,
                        )
                    elif tool_name == self.TERMINATION_TOOL:
                        self._emit_progress(
                            on_event,
                            "Compiling findings…",
                            iteration=iteration,
                            tool=tool_name,
                        )

                    tool_t0 = time.monotonic()
                    result, is_term = freshdesk_executor.execute_tool(
                        tool_name, tool_input, project_id, source_id,
                    )
                    logger.info(
                        "FRESHDESK_AGENT_TOOL exec=%s iter=%d name=%s ms=%d",
                        execution_id, iteration, tool_name,
                        int((time.monotonic() - tool_t0) * 1000),
                    )

                    if tool_name == "query_runner" and tool_input.get("sql_query"):
                        all_queries.append(tool_input["sql_query"])

                    # Treat only a dict with explicit success=False as an
                    # error block. Non-dict results (rare; e.g. a string)
                    # don't reset the counter either — they're neither a
                    # confirmed success nor a confirmed failure.
                    is_error = isinstance(result, dict) and result.get("success", True) is False
                    if is_error:
                        consecutive_errors += 1
                    elif isinstance(result, dict):
                        consecutive_errors = 0

                    if consecutive_errors >= 3:
                        return {"success": False, "error": "Too many consecutive tool errors", "sql_queries": all_queries}

                    if is_term:
                        terminated = True
                        termination_result = result

                    import json
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    })

                messages.append({"role": "user", "content": tool_results})

                logger.info(
                    "FRESHDESK_AGENT_ITER_DONE exec=%s iter=%d in_tok=%d out_tok=%d ms=%d terminated=%s",
                    execution_id, iteration,
                    usage.get("input_tokens", 0) or 0,
                    usage.get("output_tokens", 0) or 0,
                    int((time.monotonic() - iter_t0) * 1000),
                    terminated,
                )

                if terminated and termination_result:
                    return {
                        "success": True,
                        "content": termination_result.get("summary", ""),
                        "summary": termination_result.get("summary", ""),
                        "findings": termination_result.get("findings", []),
                        "recommendations": termination_result.get("recommendations", []),
                        "sql_queries": all_queries,
                        "iterations": iteration,
                        "usage": total_usage,
                    }

            # Max iterations reached
            return {"success": False, "error": f"Max iterations ({self.MAX_ITERATIONS}) reached", "sql_queries": all_queries}
        finally:
            freshdesk_executor.close()


freshdesk_analyzer_agent = FreshdeskAnalyzerAgent()
