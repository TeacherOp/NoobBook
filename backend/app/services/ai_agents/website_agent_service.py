"""
Website Agent Service - AI agent for generating complete websites.

Orchestrates the website generation workflow:
1. Agent plans the website structure (plan_website)
2. Agent generates images (generate_website_image)
3. Agent creates/updates files iteratively (create_file, read_file, update_file_lines, insert_code)
4. Agent finalizes when complete (finalize_website - termination)
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader, brand_context_loader
from app.utils import claude_parsing_utils
from app.utils.source_content_utils import get_source_content
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service
from app.services.tool_executors.website_tool_executor import website_tool_executor

logger = logging.getLogger(__name__)


class WebsiteAgentService:
    """Website generation agent - orchestration only."""

    AGENT_NAME = "website_agent"
    MAX_ITERATIONS = 30

    def __init__(self):
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("website_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    def generate_website(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "",
        edit_instructions: Optional[str] = None,
        previous_markdown: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the agent to generate a website."""
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_website_job(
            project_id, job_id,
            status="processing",
            status_message="Starting website generation..."
        )

        # Get source content — skip in edit mode since previous website already encodes it
        if previous_markdown:
            source_content = "Editing a previous website — see the PREVIOUS WEBSITE section below."
        else:
            source_content = get_source_content(project_id, source_id)

        user_message = config.get("user_message", "").format(
            source_content=source_content,
            direction=direction or "No specific direction provided - use your best judgment based on the content."
        )

        # Edit mode: append previous website content + edit instructions to user message
        if previous_markdown:
            edit_context = (
                f"\n\n=== PREVIOUS WEBSITE (refine this based on the edit instructions) ===\n"
                f"Previous Site Name: {previous_title or 'Untitled'}\n\n"
                f"{previous_markdown}\n"
                f"=== END PREVIOUS WEBSITE ===\n\n"
                f"EDIT INSTRUCTIONS: {edit_instructions or 'No specific edits requested — improve as you see fit.'}\n\n"
                f"Use the previous website as your baseline. Apply the edit instructions "
                f"to refine it. Keep elements the user didn't ask to change."
            )
            user_message += edit_context
        elif edit_instructions:
            user_message += f"\n\nADDITIONAL INSTRUCTIONS: {edit_instructions}"

        messages = [{"role": "user", "content": user_message}]

        # Load brand context if configured for presentation feature (websites use similar design)
        brand_context = brand_context_loader.load_brand_context(project_id, "presentation")
        system_prompt = config["system_prompt"]
        if brand_context:
            system_prompt = f"{system_prompt}\n\n{brand_context}"

        total_input_tokens = 0
        total_output_tokens = 0
        generated_images = []
        created_files = []

        logger.info("Starting website agent job %s", job_id[:8])

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
                        "generated_images": generated_images,
                        "created_files": created_files,
                        "iterations": iteration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens
                    }

                    # Execute tool via executor
                    result, is_termination = website_tool_executor.execute_tool(
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

        studio_index_service.update_website_job(
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
        source_id: str
    ) -> None:
        """Save execution log for debugging."""
        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Generate website (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
website_agent_service = WebsiteAgentService()
