"""
Email Agent Service - AI agent for generating HTML email templates.

Orchestrates the email template generation workflow:
1. Agent plans the template structure (plan_email_template tool)
2. Agent generates images as needed (generate_email_image tool)
3. Agent writes the final HTML code (write_email_code - termination)
"""

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
from app.services.tool_executors.email_tool_executor import email_tool_executor

logger = logging.getLogger(__name__)


class EmailAgentService:
    """Email template generation agent - orchestration only."""

    AGENT_NAME = "email_agent"
    MAX_ITERATIONS = 15

    def __init__(self):
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("email_agent")
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
        Download the primary brand logo and save it locally for the email template.

        Educational Note: Signed URLs from Supabase expire in 1 hour, but saved
        HTML needs stable URLs. We download the logo and save it to the email
        templates directory — same pattern as generated Imagen images.

        Args:
            project_id: The project UUID
            job_id: The email job UUID (used for filename prefix)
            user_id: The authenticated user's UUID (avoids project lookup)

        Returns:
            Logo info dict with filename/url/placeholder, or None if no logo
        """
        try:
            # Use provided user_id, or fall back to project lookup
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

            # Determine file extension from original filename
            original_name = logo_asset.get("file_name", "logo.png")
            ext = Path(original_name).suffix or ".png"
            logo_filename = f"{job_id}_brand_logo{ext}"

            # Upload to Supabase Storage
            # Determine content type from extension
            ext_to_mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                           ".svg": "image/svg+xml", ".gif": "image/gif", ".webp": "image/webp"}
            mime_type = ext_to_mime.get(ext.lower(), "application/octet-stream")
            storage_service.upload_studio_binary(
                project_id=project_id,
                job_type="emails",
                job_id=job_id,
                filename=logo_filename,
                file_data=logo_bytes,
                content_type=mime_type
            )

            return {
                "filename": logo_filename,
                "placeholder": "BRAND_LOGO",
                "url": f"/api/v1/projects/{project_id}/studio/email-templates/{logo_filename}"
            }

        except Exception as e:
            logger.exception("Error preparing brand logo")
            return None

    def generate_template(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "",
        user_id: str = None,
        edit_instructions: Optional[str] = None,
        previous_markdown: Optional[str] = None,
        previous_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the agent to generate an email template."""
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_email_job(
            project_id, job_id,
            status="processing",
            status_message="Starting email template generation..."
        )

        # Get source content — skip in edit mode since previous email already encodes it
        if previous_markdown:
            source_content = "Editing a previous email template — see the PREVIOUS EMAIL TEMPLATE section below."
        elif source_id:
            source_content = get_source_content(project_id, source_id, max_chars=10000)
        else:
            source_content = "No source document provided. Use the direction below as the basis for your email template."

        # Build user message from config
        effective_direction = direction if direction else config.get("default_direction", "")
        user_message = config.get("user_message", "").format(
            source_content=source_content,
            direction=effective_direction
        )

        # Load brand context if configured for email feature
        brand_context = brand_context_loader.load_brand_context(
            project_id, "email", user_id=user_id
        )
        system_prompt = config["system_prompt"]
        logo_info = None
        brand_colors = None
        brand_config = None
        if brand_context:
            system_prompt = f"{system_prompt}\n\n{brand_context}"
            # Download brand logo so it can be embedded in the email HTML
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

        # Filter brand_colors to only include user-enabled colors
        if brand_colors:
            color_enabled = brand_colors.get("enabled", {})
            brand_colors = {
                k: v for k, v in brand_colors.items()
                if k not in ("enabled", "custom") and color_enabled.get(k, True)
            }

        # Inject brand requirements directly into user message for higher priority.
        # Educational Note: Claude weights user message content higher than the tail
        # of long system prompts. By putting exact hex values and font names here,
        # the agent is far more likely to use them in the generated HTML.
        if brand_context and brand_colors:
            brand_instruction = "\n\n## BRAND REQUIREMENTS (MANDATORY)\n"
            brand_instruction += "You MUST use these exact colors in the email HTML:\n"
            if brand_colors.get("primary"):
                brand_instruction += f"- Header/sections background: {brand_colors['primary']}\n"
            if brand_colors.get("accent"):
                brand_instruction += f"- CTA buttons/links: {brand_colors['accent']}\n"
            if brand_colors.get("background"):
                brand_instruction += f"- Body background: {brand_colors['background']}\n"
            if brand_colors.get("text"):
                brand_instruction += f"- Text color: {brand_colors['text']}\n"
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
                    'style="max-height:60px;width:auto;"> in the header\n'
                )
            brand_instruction += "Do NOT substitute these with any other colors, fonts, or skip the logo.\n"
            user_message = user_message + brand_instruction

        # Edit mode: append previous email content + edit instructions to user message
        if previous_markdown:
            edit_context = (
                f"\n\n=== PREVIOUS EMAIL TEMPLATE (refine this based on the edit instructions) ===\n"
                f"Previous Title: {previous_title or 'Untitled'}\n\n"
                f"{previous_markdown}\n"
                f"=== END PREVIOUS EMAIL TEMPLATE ===\n\n"
                f"EDIT INSTRUCTIONS: {edit_instructions or 'No specific edits requested — improve as you see fit.'}\n\n"
                f"Use the previous email template as your baseline. Apply the edit instructions "
                f"to refine it. Keep elements the user didn't ask to change."
            )
            user_message += edit_context
        elif edit_instructions:
            # No parent content but user provided edit instructions — treat as additional guidance
            user_message += f"\n\nADDITIONAL INSTRUCTIONS: {edit_instructions}"

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0
        generated_images = []  # Track generated images across tool calls

        logger.info("Starting email agent job %s", job_id[:8])

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
                        "logo_info": logo_info,
                        "brand_colors": brand_colors,
                        "iterations": iteration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens
                    }

                    # Execute tool via executor
                    result, is_termination = email_tool_executor.execute_tool(
                        tool_name, tool_input, context
                    )

                    # Track new images from generate_email_image
                    if tool_name == "generate_email_image" and result.get("image_info"):
                        generated_images.append(result["image_info"])

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

        studio_index_service.update_email_job(
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
            task=f"Generate email template (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
email_agent_service = EmailAgentService()
