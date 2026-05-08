"""
Component Agent Service - AI agent for generating UI component variations.

Orchestrates the component generation workflow:
1. Agent plans 2-4 component variations (plan_components tool)
2. Agent writes complete HTML/CSS/JS code for all variations (write_component_code - termination)
"""

import base64
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader, brand_context_loader
from app.utils import claude_parsing_utils
from app.utils.source_content_utils import get_source_content
from app.services.data_services import message_service, project_service
from app.services.data_services.brand_asset_service import brand_asset_service
from app.services.data_services.brand_config_service import brand_config_service
from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service
from app.services.tool_executors.component_tool_executor import component_tool_executor

logger = logging.getLogger(__name__)


class ComponentAgentService:
    """Component generation agent - orchestration only."""

    AGENT_NAME = "component_agent"
    MAX_ITERATIONS = 10

    def __init__(self):
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("component_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    def _prepare_brand_logo(
        self,
        project_id: str,
        job_id: str,
        user_id: str = None
    ) -> Optional[Dict[str, str]]:
        """
        Download the primary brand logo and save it locally for the component HTML.

        Educational Note: Same pattern as email agent — signed URLs from Supabase
        expire, but saved HTML needs stable URLs. We download the logo and save it
        to the component job directory alongside the HTML files.

        Returns:
            Logo info dict with filename/url/placeholder, or None if no logo
        """
        try:
            if not user_id:
                project = project_service.get_project(project_id)
                if not project:
                    return None
                user_id = project.get("user_id")
            if not user_id:
                return None

            # Get primary logo asset metadata
            logo_asset = brand_asset_service.get_primary_asset(user_id, "logo")
            if not logo_asset:
                return None

            # Download logo bytes from Supabase storage
            logo_bytes = storage_service.download_brand_asset(
                user_id=user_id,
                asset_id=logo_asset["id"],
                filename=logo_asset["file_name"]
            )
            if not logo_bytes:
                logger.warning("Could not download brand logo")
                return None

            # Build base64 data URI so the logo renders inside iframes
            # without needing an authenticated request back to the server.
            original_name = logo_asset.get("file_name", "logo.png")
            mime = logo_asset.get("mime_type", "image/png")
            b64 = base64.b64encode(logo_bytes).decode("ascii")
            data_uri = f"data:{mime};base64,{b64}"

            return {
                "filename": original_name,
                "placeholder": "BRAND_LOGO",
                "url": data_uri
            }

        except Exception as e:
            logger.exception("Error preparing brand logo")
            return None

    def generate_components(
        self,
        project_id: str,
        source_id: Optional[str],
        job_id: str,
        direction: str = "",
        user_id: str = None,
        previous_components: Optional[Dict[str, Any]] = None,
        edit_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the agent to generate component variations."""
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_component_job(
            project_id, job_id,
            status="processing",
            status_message="Starting component generation..."
        )

        # Get source content (optional — can generate from direction alone)
        source_content = ""
        if source_id:
            source_content = get_source_content(project_id, source_id, max_chars=15000)

        # Build user message from config
        effective_direction = direction if direction else config.get("default_direction", "")
        if source_content:
            user_message = config.get("user_message", "").format(
                source_content=source_content,
                direction=effective_direction
            )
        else:
            user_message = (
                f"Create 2-4 professional UI component variations based on this direction:\n\n"
                f"Direction: {effective_direction}\n\n"
                f"Please create complete, production-ready components following the workflow:\n"
                f"1. Plan 2-4 distinct component variations (different styles, not just colors)\n"
                f"2. Write complete HTML/CSS/JS code for each variation (self-contained HTML documents)\n"
                f"3. Make each variation unique and professional"
            )

        # Edit mode: append previous component info and edit instructions
        if previous_components and edit_instructions:
            edit_context = "\n\n## EDIT MODE — REFINE PREVIOUS COMPONENTS\n"
            edit_context += f"Category: {previous_components.get('component_category', 'N/A')}\n"
            edit_context += f"Description: {previous_components.get('component_description', 'N/A')}\n"
            edit_context += "Previous variations:\n"
            for v in previous_components.get("variations", []):
                edit_context += f"- {v['variation_name']}: {v['description']}\n"
            edit_context += f"\nEDIT INSTRUCTIONS: {edit_instructions}\n"
            edit_context += "Refine the above components based on the edit instructions. Keep the same category and number of variations unless the edit instructs otherwise."
            user_message = user_message + edit_context
        elif edit_instructions:
            user_message = user_message + f"\n\nADDITIONAL INSTRUCTIONS: {edit_instructions}"

        # Load brand context if configured for ads_creative feature
        brand_context = brand_context_loader.load_brand_context(
            project_id, "ads_creative", user_id=user_id
        )
        system_prompt = config["system_prompt"]
        logo_info = None
        brand_colors = None
        brand_config = None
        if brand_context:
            system_prompt = f"{system_prompt}\n\n{brand_context}"
            # Download brand logo so it can be embedded in the component HTML
            logo_info = self._prepare_brand_logo(project_id, job_id, user_id=user_id)
            # Extract brand colors for plan validation in the tool executor
            if user_id:
                brand_config = brand_config_service.get_config(user_id) or {}
                brand_colors = brand_config.get("colors")
            else:
                project = project_service.get_project(project_id)
                if project and project.get("user_id"):
                    brand_config = brand_config_service.get_config(project["user_id"]) or {}
                    brand_colors = brand_config.get("colors")

        # Filter brand_colors to only include user-enabled colors.
        # Educational Note: Users can toggle individual colors off in Settings > Design.
        # Disabled colors are omitted from the brand instruction and CSS override so
        # the agent picks its own values for those slots.
        if brand_colors:
            color_enabled = brand_colors.get("enabled", {})
            brand_colors = {
                k: v for k, v in brand_colors.items()
                if k not in ("enabled", "custom") and color_enabled.get(k, True)
            }

        # Inject brand requirements directly into user message for higher priority.
        # Educational Note: Claude weights user message content higher than the tail
        # of long system prompts. By putting exact hex values here mapped to CSS
        # custom properties, the agent is far more likely to use them in the HTML.
        if brand_context and brand_colors:
            brand_instruction = "\n\n## BRAND REQUIREMENTS (MANDATORY)\n"
            brand_instruction += "You MUST use these exact colors as CSS custom properties in :root:\n"
            if brand_colors.get("primary"):
                brand_instruction += f"- --primary-color: {brand_colors['primary']}\n"
            if brand_colors.get("accent"):
                brand_instruction += f"- --accent-color: {brand_colors['accent']}\n"
            if brand_colors.get("secondary"):
                brand_instruction += f"- --secondary-color: {brand_colors['secondary']}\n"
            if brand_colors.get("background"):
                brand_instruction += f"- --bg-color: {brand_colors['background']}\n"
            if brand_colors.get("text"):
                brand_instruction += f"- --text-color: {brand_colors['text']}\n"
            # Typography
            if brand_config:
                typography = brand_config.get("typography", {})
                if typography.get("heading_font"):
                    brand_instruction += f"- Heading font: {typography['heading_font']}\n"
                if typography.get("body_font"):
                    brand_instruction += f"- Body font: {typography['body_font']}\n"
            # Logo
            if logo_info:
                brand_instruction += (
                    '- Logo: Include <img src="BRAND_LOGO" alt="Logo" '
                    'style="max-height:48px;width:auto;"> in the component header\n'
                )
            brand_instruction += "All variations MUST use the same brand colors — vary layout/style, not the color palette.\n"
            brand_instruction += "Do NOT substitute these with any other colors, fonts, or skip the logo.\n"
            user_message = user_message + brand_instruction

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0

        logger.info("Starting component agent job %s", job_id[:8])

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
                        "logo_info": logo_info,
                        "brand_colors": brand_colors,
                        "iterations": iteration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens
                    }

                    # Execute tool via executor
                    result, is_termination = component_tool_executor.execute_tool(
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

        studio_index_service.update_component_job(
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
            task=f"Generate components (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
component_agent_service = ComponentAgentService()
