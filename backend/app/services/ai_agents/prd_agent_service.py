"""
PRD Agent Service - AI agent for generating Product Requirements Documents.

Orchestrates the PRD generation workflow:
1. Agent plans the PRD structure (plan_prd tool)
2. Agent writes sections incrementally (write_prd_section tool - can be called multiple times)
3. Agent signals completion via is_last_section=true flag

The markdown output can be rendered on frontend and exported to PDF.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.source_content_utils import get_source_content
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service
from app.services.tool_executors.prd_tool_executor import prd_tool_executor

logger = logging.getLogger(__name__)


class PRDAgentService:
    """PRD generation agent - orchestration only."""

    AGENT_NAME = "prd_agent"
    MAX_ITERATIONS = 15  # Detailed PRDs: 1 plan + 6-8 sections

    def __init__(self):
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("prd_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    def generate_prd(
        self,
        project_id: str,
        source_id: Optional[str],
        job_id: str,
        direction: str = "",
        previous_document: Optional[Dict] = None,
        edit_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the agent to generate a PRD document."""
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_prd_job(
            project_id, job_id,
            status="processing",
            status_message="Starting PRD generation...",
            started_at=started_at
        )

        # Get source content (if source provided)
        source_content = ""
        if source_id:
            source_content = get_source_content(project_id, source_id, max_chars=15000)

        # Build user message from config or direction-only fallback
        # Guard against error messages AND unprocessed sources (e.g., "Content not yet processed")
        effective_direction = direction if direction else config.get("default_direction", "")
        has_valid_content = (source_content
                            and not source_content.startswith("Error")
                            and "not yet processed" not in source_content)
        if has_valid_content:
            user_message = config.get("user_message", "").format(
                source_content=source_content,
                direction=effective_direction
            )
        else:
            user_message = f"Create a comprehensive Product Requirements Document (PRD).\n\nDirection from user: {effective_direction}\n\nPlease create a detailed, complete PRD following the workflow:\n1. First, plan the document structure using the plan_prd tool\n2. Then write each section one at a time using the write_prd_section tool\n3. Set is_last_section=true when you write the final section"

        # Edit mode: include previous document for refinement (capped to control token costs)
        if previous_document and edit_instructions:
            prev_markdown = previous_document.get('markdown_content', '')
            if len(prev_markdown) > 15000:
                prev_markdown = prev_markdown[:15000] + "\n\n[... document truncated for context limit ...]"
            edit_context = "\n\n## EDIT MODE — REFINE PREVIOUS DOCUMENT\n"
            edit_context += f"Previous document title: {previous_document.get('document_title', 'N/A')}\n"
            edit_context += f"Previous sections: {previous_document.get('sections_written', 0)}\n"
            edit_context += "\n### PREVIOUS DOCUMENT CONTENT:\n"
            edit_context += prev_markdown
            edit_context += f"\n\n### EDIT INSTRUCTIONS:\n{edit_instructions}\n"
            edit_context += "Rewrite the document applying the edit instructions. Preserve sections and content the user didn't ask to change. Focus modifications on what the edit instructions specify."
            user_message = user_message + edit_context
        elif edit_instructions:
            user_message = user_message + f"\n\nADDITIONAL INSTRUCTIONS: {edit_instructions}"

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0
        sections_written = 0

        logger.info("Starting PRD agent job %s", job_id[:8])

        for iteration in range(1, self.MAX_ITERATIONS + 1):

            response = claude_service.send_message(
                messages=messages,
                system_prompt=config["system_prompt"],
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
                        "sections_written": sections_written,
                        "iterations": iteration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens
                    }

                    # Execute tool via executor
                    result, is_termination = prd_tool_executor.execute_tool(
                        tool_name, tool_input, context
                    )

                    # Track sections written
                    if tool_name == "write_prd_section":
                        sections_written += 1

                    if is_termination:
                        logger.info("Completed in %d iterations, %d sections", iteration, sections_written)
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
            "sections_written": sections_written,
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
        }

        studio_index_service.update_prd_job(
            project_id, job_id,
            status="error",
            error_message=error_result["error_message"]
        )

        self._save_execution(
            project_id, execution_id, job_id, messages,
            error_result, started_at, source_id
        )

        return error_result

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        job_id: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: Optional[str]
    ) -> None:
        """Save execution log for debugging."""
        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Generate PRD (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
prd_agent_service = PRDAgentService()
