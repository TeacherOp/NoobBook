"""
Business Report Agent Service - AI agent for generating data-driven business reports.

Orchestrates the business report generation workflow:
1. Agent plans the report structure (plan_business_report)
2. Agent calls csv_analyzer_agent for data analysis (analyze_csv_data)
3. Agent searches non-CSV sources for context (search_source_content)
4. Agent writes the final markdown report (write_business_report - termination)
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader, brand_context_loader
from app.utils import claude_parsing_utils
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service
from app.services.tool_executors.business_report_tool_executor import business_report_tool_executor

logger = logging.getLogger(__name__)


class BusinessReportAgentService:
    """Business report generation agent - orchestration only."""

    AGENT_NAME = "business_report_agent"
    MAX_ITERATIONS = 15

    def __init__(self):
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("business_report_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    def generate_business_report(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "",
        report_type: str = "executive_summary",
        csv_source_ids: List[str] = None,
        context_source_ids: List[str] = None,
        focus_areas: List[str] = None,
        edit_instructions: Optional[str] = None,
        previous_markdown: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the agent to generate a business report."""
        config = self._load_config()
        tools = self._load_tools()

        csv_source_ids = csv_source_ids or []
        context_source_ids = context_source_ids or []
        focus_areas = focus_areas or []

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_business_report_job(
            project_id, job_id,
            status="processing",
            status_message="Starting business report generation...",
            started_at=started_at
        )

        # Get source information and build user message
        source_info = self._get_source_info(project_id, csv_source_ids, context_source_ids)
        report_types = config.get("report_types", {})
        report_type_display = report_types.get(report_type, report_type.replace("_", " ").title())

        user_message = self._build_user_message(
            config, source_info, report_type_display, direction, focus_areas
        )

        # Edit mode: append previous report and edit instructions to user message
        if edit_instructions and previous_markdown:
            edit_context = f"\n\n## EDIT MODE\n\nYou are editing a previously generated report. Apply the user's edit instructions to refine the report.\n\n### Previous Report Title: {previous_title or 'Untitled'}\n\n### Previous Report Content:\n{previous_markdown}\n\n### Edit Instructions:\n{edit_instructions}\n\nStart from the previous content as your baseline. Apply the edit instructions to refine the report. Keep elements the user didn't ask to change. Focus changes on what the edit instructions specify. You may still call analyze_csv_data if the edit requires new data analysis or charts."
            user_message += edit_context

        messages = [{"role": "user", "content": user_message}]

        # Load brand context if configured for business_report feature
        brand_context = brand_context_loader.load_brand_context(project_id, "business_report")
        system_prompt = config["system_prompt"]
        if brand_context:
            system_prompt = f"{system_prompt}\n\n{brand_context}"

        total_input_tokens = 0
        total_output_tokens = 0
        collected_charts = []
        collected_analyses = []

        logger.info("Starting business report agent job %s, type=%s", job_id[:8], report_type)

        for iteration in range(1, self.MAX_ITERATIONS + 1):

            response = claude_service.send_message(
                messages=messages,
                system_prompt=system_prompt,
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=tools["all_tools"] if isinstance(tools, dict) else tools,
                tool_choice={"type": "any"},
                project_id=project_id
            )

            total_input_tokens += response["usage"]["input_tokens"]
            total_output_tokens += response["usage"]["output_tokens"]

            content_blocks = response.get("content_blocks", [])
            serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
            messages.append({"role": "assistant", "content": serialized_content})

            # Process tool calls
            tool_results = []

            for block in content_blocks:
                block_type = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")

                if block_type == "tool_use":
                    tool_name = getattr(block, "name", "") if hasattr(block, "name") else block.get("name", "")
                    tool_input = getattr(block, "input", {}) if hasattr(block, "input") else block.get("input", {})
                    tool_id = getattr(block, "id", "") if hasattr(block, "id") else block.get("id", "")

                    # Build execution context
                    context = {
                        "project_id": project_id,
                        "job_id": job_id,
                        "source_id": source_id,
                        "collected_charts": collected_charts,
                        "collected_analyses": collected_analyses,
                        "iterations": iteration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "report_type": report_type
                    }

                    # Execute tool via executor
                    result, is_termination = business_report_tool_executor.execute_tool(
                        tool_name, tool_input, context
                    )

                    if is_termination:
                        logger.info("Completed in %d iterations", iteration)
                        self._save_execution(
                            project_id, execution_id, job_id, messages,
                            result, started_at, source_id
                        )
                        return result

                    # Add tool result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result.get("message", str(result))
                    })

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

        studio_index_service.update_business_report_job(
            project_id, job_id,
            status="error",
            error_message=error_result["error_message"]
        )

        self._save_execution(
            project_id, execution_id, job_id, messages,
            error_result, started_at, source_id
        )

        return error_result

    def _get_source_info(
        self,
        project_id: str,
        csv_source_ids: List[str],
        context_source_ids: List[str]
    ) -> Dict[str, Any]:
        """Get information about available sources."""
        try:
            from app.services.source_services import source_service

            csv_sources = []
            for source_id in csv_source_ids:
                source = source_service.get_source(project_id, source_id)
                if source:
                    csv_sources.append({
                        "source_id": source_id,
                        "name": source.get("name", "Unknown"),
                        "type": "csv"
                    })

            context_sources = []
            for source_id in context_source_ids:
                source = source_service.get_source(project_id, source_id)
                if source:
                    context_sources.append({
                        "source_id": source_id,
                        "name": source.get("name", "Unknown"),
                        "type": source.get("file_extension", "unknown")
                    })

            return {
                "csv_sources": csv_sources,
                "context_sources": context_sources
            }

        except Exception as e:
            logger.exception("Error getting source info")
            return {"csv_sources": [], "context_sources": []}

    def _build_user_message(
        self,
        config: Dict[str, Any],
        source_info: Dict[str, Any],
        report_type_display: str,
        direction: str,
        focus_areas: List[str]
    ) -> str:
        """Build the initial user message using config template."""
        # Build CSV sources section
        csv_sources = source_info.get("csv_sources", [])
        if csv_sources:
            csv_lines = ["CSV DATA SOURCES:"]
            for src in csv_sources:
                csv_lines.append(f"- {src['name']} (source_id: {src['source_id']})")
            csv_sources_section = "\n".join(csv_lines)
        else:
            csv_sources_section = ""

        # Build context sources section
        context_sources = source_info.get("context_sources", [])
        if context_sources:
            ctx_lines = ["CONTEXT SOURCES (optional):"]
            for src in context_sources:
                ctx_lines.append(f"- {src['name']} (source_id: {src['source_id']})")
            context_sources_section = "\n".join(ctx_lines)
        else:
            context_sources_section = ""

        # Build focus areas section
        if focus_areas:
            focus_areas_section = "FOCUS ON: " + ", ".join(focus_areas)
        else:
            focus_areas_section = ""

        # Build direction section
        if direction:
            direction_section = f"NOTE: {direction}"
        else:
            direction_section = ""

        # Format user message from config
        user_message = config.get("user_message", "").format(
            report_type_display=report_type_display,
            csv_sources_section=csv_sources_section,
            context_sources_section=context_sources_section,
            focus_areas_section=focus_areas_section,
            direction_section=direction_section
        )

        return user_message

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        job_id: str,
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
            task=f"Generate business report (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
business_report_agent_service = BusinessReportAgentService()
