"""
Mixpanel Analyzer Agent Executor - Bridge between main_chat_service and
the agent. Mirrors freshdesk_analyzer_agent_executor.

Formats the agent's structured result (summary + findings +
recommendations) into a single markdown string the main chat can hand
back to Claude as a tool_result.
"""

import logging
from typing import Any, Callable, Dict, Optional

from app.services.ai_agents.mixpanel_analyzer_agent import mixpanel_analyzer_agent

logger = logging.getLogger(__name__)


def execute(
    project_id: str,
    source_id: str,
    query: str,
    chat_id: Optional[str] = None,
    user_id: Optional[str] = None,
    on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Run the Mixpanel analysis agent and format its output for chat.

    ``on_event`` is threaded through so per-iteration ``tool_progress``
    events reach the SSE stream and the chat panel can show specific
    progress messages while the agent works.
    """
    try:
        result = mixpanel_analyzer_agent.run(
            project_id=project_id,
            source_id=source_id,
            query=query,
            chat_id=chat_id,
            user_id=user_id,
            on_event=on_event,
        )

        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Analysis failed")}

        parts = []

        summary = result.get("summary") or result.get("content", "")
        if summary:
            parts.append(summary)

        findings = result.get("findings", [])
        if findings:
            parts.append("\n**Key Findings:**")
            for f in findings:
                parts.append(f"- {f}")

        recommendations = result.get("recommendations", [])
        if recommendations:
            parts.append("\n**Recommendations:**")
            for r in recommendations:
                parts.append(f"- {r}")

        content = "\n".join(parts) if parts else "Analysis complete but no results generated."

        return {
            "success": True,
            "content": content,
            "queries": result.get("queries", []),
            "iterations": result.get("iterations", 0),
            "usage": result.get("usage", {}),
        }

    except Exception as e:
        logger.exception("Mixpanel analysis failed for source %s", source_id)
        return {"success": False, "error": str(e)}
