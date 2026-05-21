"""
Mixpanel Analyzer Agent - Agentic loop for product-usage questions.

Mirrors freshdesk_analyzer_agent.py. Claude iterates with a fixed tool
set (list_events, query_events, segmentation, list_funnels, query_funnel,
retention, events_after) until it calls return_mixpanel_analysis to
terminate with structured output.
"""

import json
import logging
import time
import uuid
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import prompt_loader, tool_loader
from app.services.integrations.claude import claude_service
from app.services.integrations.knowledge_bases.mixpanel import mixpanel_service
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class MixpanelAnalyzerAgent:
    AGENT_NAME = "mixpanel_analyzer_agent"
    MAX_ITERATIONS = 40
    TERMINATION_TOOL = "return_mixpanel_analysis"
    # Cap each tool_result payload sent back to Claude so a single noisy
    # call (long-window query_events, large segmentation, or the heavy
    # events_after /export cohort) can't blow the context window or
    # spike per-iteration cost. The old _format_mixpanel_data helper in
    # knowledge_base_service used the same 15000-char limit; we preserve
    # it here now that the agent owns the serialization step.
    MAX_TOOL_RESULT_CHARS = 15_000

    def __init__(self):
        self._tools: Optional[List[Dict[str, Any]]] = None

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_from_category("mixpanel_agent")
        return self._tools

    @staticmethod
    def _default_date_window(tool_input: Dict[str, Any]) -> Tuple[str, str]:
        """Fall back to yesterday→today when Claude forgot to pass dates.

        Mirrors the same helper that used to live in knowledge_base_service
        for the direct-tool path. The agent's system prompt asks Claude to
        always supply concrete YYYY-MM-DD dates, but this guard makes a
        late-stage forgetfulness recoverable instead of returning a 400.
        """
        today = date.today()
        yesterday = today - timedelta(days=1)
        from_date = tool_input.get("from_date") or yesterday.isoformat()
        to_date = tool_input.get("to_date") or today.isoformat()
        if from_date > to_date:
            from_date = to_date
        return from_date, to_date

    @classmethod
    def _serialize_tool_result(cls, result: Any) -> str:
        """JSON-encode a tool result, truncating with a marker if it
        exceeds MAX_TOOL_RESULT_CHARS.

        Mixpanel's Query API can return tens of KB for a long-window
        query_events call, and events_after's /export pass can return
        hundreds of KB. Forwarding that verbatim into the next iteration
        would risk a context-overflow error or sharp cost spikes. We
        truncate to a fixed character budget and append a visible marker
        so Claude knows the payload is incomplete and can narrow the
        next call (date window, top_n, etc.)."""
        if isinstance(result, dict):
            try:
                encoded = json.dumps(result, default=str)
            except (TypeError, ValueError):
                encoded = str(result)
        else:
            encoded = str(result)
        if len(encoded) > cls.MAX_TOOL_RESULT_CHARS:
            return encoded[: cls.MAX_TOOL_RESULT_CHARS] + "\n... (truncated — payload exceeded size cap; narrow the date range, top_n, or property filter)"
        return encoded

    @staticmethod
    def _emit_progress(
        on_event: Optional[Callable[[str, Dict[str, Any]], None]],
        message: str,
        *,
        iteration: Optional[int] = None,
        tool: Optional[str] = None,
    ) -> None:
        """Best-effort SSE progress emit. Mirrors freshdesk_analyzer_agent."""
        if on_event is None:
            return
        try:
            payload: Dict[str, Any] = {"agent": "mixpanel", "message": message}
            if iteration is not None:
                payload["iteration"] = iteration
            if tool is not None:
                payload["tool"] = tool
            on_event("tool_progress", payload)
        except Exception:
            logger.debug("tool_progress emit failed", exc_info=True)

    def _execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """Dispatch a single tool call to the underlying mixpanel_service.

        Returns ``(result_dict, is_termination)``. Mirrors the shape of
        ``freshdesk_executor.execute_tool``. Termination is signalled by
        the return_mixpanel_analysis tool, whose input becomes the result
        verbatim (the agent loop reads ``summary`` / ``findings`` /
        ``recommendations`` straight from it).
        """
        if tool_name == self.TERMINATION_TOOL:
            return tool_input, True

        if tool_name == "mixpanel_list_events":
            limit = tool_input.get("limit", 100)
            return mixpanel_service.list_events(limit=limit), False

        if tool_name == "mixpanel_query_events":
            from_date, to_date = self._default_date_window(tool_input)
            return (
                mixpanel_service.query_events(
                    event_names=tool_input.get("event_names") or [],
                    from_date=from_date,
                    to_date=to_date,
                    unit=tool_input.get("unit", "day"),
                ),
                False,
            )

        if tool_name == "mixpanel_segmentation":
            from_date, to_date = self._default_date_window(tool_input)
            return (
                mixpanel_service.segmentation(
                    event=tool_input.get("event"),
                    from_date=from_date,
                    to_date=to_date,
                    on=tool_input.get("on"),
                    where=tool_input.get("where"),
                    unit=tool_input.get("unit", "day"),
                ),
                False,
            )

        if tool_name == "mixpanel_list_funnels":
            return mixpanel_service.list_funnels(), False

        if tool_name == "mixpanel_query_funnel":
            from_date, to_date = self._default_date_window(tool_input)
            return (
                mixpanel_service.query_funnel(
                    funnel_id=tool_input.get("funnel_id"),
                    from_date=from_date,
                    to_date=to_date,
                    unit=tool_input.get("unit", "day"),
                ),
                False,
            )

        if tool_name == "mixpanel_retention":
            from_date, to_date = self._default_date_window(tool_input)
            return (
                mixpanel_service.retention(
                    born_event=tool_input.get("born_event"),
                    event=tool_input.get("event"),
                    from_date=from_date,
                    to_date=to_date,
                    retention_type=tool_input.get("retention_type", "birth"),
                    unit=tool_input.get("unit", "day"),
                ),
                False,
            )

        if tool_name == "mixpanel_events_after":
            from_date, to_date = self._default_date_window(tool_input)
            return (
                mixpanel_service.events_after(
                    trigger_event=tool_input.get("trigger_event"),
                    from_date=from_date,
                    to_date=to_date,
                    window_hours=tool_input.get("window_hours", 168),
                    top_n=tool_input.get("top_n", 20),
                    exclude_trigger=tool_input.get("exclude_trigger", True),
                ),
                False,
            )

        return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def run(
        self,
        project_id: str,
        source_id: str,
        query: str,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Run the Mixpanel analysis agentic loop."""
        execution_id = str(uuid.uuid4())[:8]
        logger.info(
            "[MixpanelAgent:%s] Starting analysis for source %s", execution_id, source_id
        )
        self._emit_progress(on_event, "Connecting to Mixpanel…")

        if not mixpanel_service.is_configured():
            return {
                "success": False,
                "error": (
                    "Mixpanel isn't configured on this server. Set "
                    "MIXPANEL_SERVICE_ACCOUNT_USERNAME, "
                    "MIXPANEL_SERVICE_ACCOUNT_SECRET, and MIXPANEL_PROJECT_ID "
                    "in the backend env and redeploy."
                ),
            }

        prompt_config = prompt_loader.get_prompt_config(self.AGENT_NAME)
        tools = self._load_tools()

        # Ground the agent in today's date — "yesterday", "last 7 days", etc.
        # are otherwise impossible to resolve to the YYYY-MM-DD that Mixpanel
        # demands. Mirrors the freshdesk agent's runtime injection.
        today_line = f"Today's date: {date.today().isoformat()}"
        system_prompt = f"{today_line}\n\n{prompt_config.get('system_prompt', '')}"
        model = prompt_config.get("model", "claude-sonnet-4-6")
        max_tokens = prompt_config.get("max_tokens", 4096)
        temperature = prompt_config.get("temperature", 0.0)

        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": f"Mixpanel source ID: {source_id}\n\nUser question: {query}",
            }
        ]

        total_usage = {"input_tokens": 0, "output_tokens": 0}
        all_queries: List[Dict[str, Any]] = []
        consecutive_errors = 0

        for iteration in range(1, self.MAX_ITERATIONS + 1):
            iter_t0 = time.monotonic()
            logger.info(
                "MIXPANEL_AGENT_ITER exec=%s iter=%d", execution_id, iteration
            )
            self._emit_progress(
                on_event,
                f"Analyzing Mixpanel data (step {iteration})…",
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
                    "queries": all_queries,
                    "iterations": iteration,
                    "usage": total_usage,
                }

            if not claude_parsing_utils.is_tool_use(response):
                text = claude_parsing_utils.extract_text(response)
                return {
                    "success": True,
                    "content": text,
                    "iterations": iteration,
                    "usage": total_usage,
                }

            tool_blocks = claude_parsing_utils.extract_tool_use_blocks(response)
            content_blocks = response.get("content_blocks", [])
            messages.append({"role": "assistant", "content": content_blocks})

            tool_results: List[Dict[str, Any]] = []
            terminated = False
            termination_result: Optional[Dict[str, Any]] = None

            for block in tool_blocks:
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                tool_id = block.get("id", "")

                # Specific per-tool progress so the chat panel can show
                # "Listing events…", "Querying funnel…", etc. instead of
                # the generic "Analyzing…".
                if tool_name == "mixpanel_list_events":
                    self._emit_progress(on_event, "Listing Mixpanel events…", iteration=iteration, tool=tool_name)
                elif tool_name == "mixpanel_query_events":
                    self._emit_progress(on_event, "Querying event counts…", iteration=iteration, tool=tool_name)
                elif tool_name == "mixpanel_segmentation":
                    self._emit_progress(on_event, "Segmenting event by property…", iteration=iteration, tool=tool_name)
                elif tool_name == "mixpanel_list_funnels":
                    self._emit_progress(on_event, "Listing funnels…", iteration=iteration, tool=tool_name)
                elif tool_name == "mixpanel_query_funnel":
                    self._emit_progress(on_event, "Querying funnel conversion…", iteration=iteration, tool=tool_name)
                elif tool_name == "mixpanel_retention":
                    self._emit_progress(on_event, "Computing retention…", iteration=iteration, tool=tool_name)
                elif tool_name == "mixpanel_events_after":
                    self._emit_progress(on_event, "Running cohort path analysis…", iteration=iteration, tool=tool_name)
                elif tool_name == self.TERMINATION_TOOL:
                    self._emit_progress(on_event, "Compiling findings…", iteration=iteration, tool=tool_name)

                tool_t0 = time.monotonic()
                result, is_term = self._execute_tool(tool_name, tool_input)
                logger.info(
                    "MIXPANEL_AGENT_TOOL exec=%s iter=%d name=%s ms=%d",
                    execution_id, iteration, tool_name,
                    int((time.monotonic() - tool_t0) * 1000),
                )

                # Record each non-termination call for the audit trail
                # surfaced in the executor's return payload.
                if not is_term:
                    all_queries.append({"tool": tool_name, "input": tool_input})

                # Same consecutive-error guard as the freshdesk agent — a
                # broken event name or bad date can otherwise burn the
                # whole iteration budget before the agent gives up.
                is_error = isinstance(result, dict) and result.get("success", True) is False
                if is_error:
                    consecutive_errors += 1
                elif isinstance(result, dict):
                    consecutive_errors = 0

                if consecutive_errors >= 3:
                    return {
                        "success": False,
                        "error": "Too many consecutive tool errors",
                        "queries": all_queries,
                    }

                if is_term:
                    terminated = True
                    termination_result = result

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": self._serialize_tool_result(result),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

            logger.info(
                "MIXPANEL_AGENT_ITER_DONE exec=%s iter=%d in_tok=%d out_tok=%d ms=%d terminated=%s",
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
                    "findings": termination_result.get("findings", []) or [],
                    "recommendations": termination_result.get("recommendations", []) or [],
                    "queries": all_queries,
                    "iterations": iteration,
                    "usage": total_usage,
                }

        return {
            "success": False,
            "error": f"Max iterations ({self.MAX_ITERATIONS}) reached",
            "queries": all_queries,
        }


mixpanel_analyzer_agent = MixpanelAnalyzerAgent()
