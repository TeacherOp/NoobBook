"""
Infographic Service - Generates visual infographics from source content.

Educational Note: This service implements a two-step AI pipeline:
1. Claude analyzes source content and creates a detailed image prompt
2. Google Gemini generates the infographic image

Infographics are visual summaries that organize information in an
educational, easy-to-scan format with icons, sections, and visual flow.
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service

logger = logging.getLogger(__name__)
from app.services.integrations.google.imagen_service import imagen_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.services.studio_services.partial_image_utils import make_partial_callback
from app.config import prompt_loader, brand_context_loader
from app.services.integrations.supabase import storage_service


# Infographic aspect ratio - landscape for modal display
INFOGRAPHIC_ASPECT_RATIO = "16:9"


class InfographicService:
    """
    Service for generating infographic images from source content.

    Educational Note: This service orchestrates the full pipeline:
    1. Read and sample source content
    2. Claude generates infographic layout and image prompt
    3. Gemini generates the visual infographic image
    """

    def __init__(self):
        """Initialize service with lazy-loaded config."""
        self._prompt_config = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("infographic")
        return self._prompt_config

    def _get_source_content(
        self,
        project_id: str,
        source_id: str,
        max_tokens: int = 8000
    ) -> str:
        """
        Get source content for infographic generation.

        Educational Note: For large sources, we sample chunks evenly
        to stay within token limits while covering the full content.
        Content is downloaded from Supabase Storage.
        """
        # Get source metadata
        source = source_index_service.get_source_from_index(project_id, source_id)
        if not source:
            return ""

        # Token count is stored in embedding_info
        embedding_info = source.get("embedding_info", {}) or {}
        token_count = embedding_info.get("token_count", 0) or 0

        # For small sources, read the processed file from Supabase Storage
        if token_count < max_tokens:
            processed_content = storage_service.download_processed_file(
                project_id, source_id
            )
            if processed_content:
                return processed_content

        # For large sources, get chunks from Supabase Storage
        chunks = storage_service.list_source_chunks(project_id, source_id)
        if not chunks:
            return ""

        # Sample evenly across chunks
        total_chunks = len(chunks)
        sample_count = min(20, total_chunks)  # Max 20 chunks
        step = max(1, total_chunks // sample_count)

        content_parts = []
        for i in range(0, total_chunks, step):
            if len(content_parts) >= sample_count:
                break
            chunk_text = chunks[i].get("text", "")
            content_parts.append(chunk_text.strip())

        return '\n\n---\n\n'.join(content_parts)

    def generate_infographic(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "",
        logo_image_bytes: Optional[bytes] = None,
        logo_mime_type: str = "image/png",
        user_id: Optional[str] = None,
        edit_instructions: Optional[str] = None,
        previous_image_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an infographic image for a source.

        Educational Note: This is the main orchestrator that:
        1. Reads source content
        2. Uses Claude to generate image prompt details
        3. Uses Gemini to generate the infographic image
        4. Updates job status throughout

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: Additional context/direction from the user

        Returns:
            Dict with success status, image data, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_infographic_job(
            project_id, job_id,
            status="processing",
            progress="Reading source content...",
            started_at=datetime.now().isoformat()
        )

        try:
            # Get source content if a source is provided
            content = ""
            if source_id:
                source = source_index_service.get_source_from_index(project_id, source_id)
                if not source:
                    raise ValueError(f"Source {source_id} not found")
                content = self._get_source_content(project_id, source_id)

            # Step 1: Generate image prompt with Claude
            studio_index_service.update_infographic_job(
                project_id, job_id,
                progress="Designing infographic layout..."
            )

            # Load brand context — only use logo if brand is enabled
            brand_context = brand_context_loader.load_brand_context(
                project_id, "infographic", user_id=user_id
            )
            effective_logo = logo_image_bytes if brand_context else None

            prompt_result = self._generate_image_prompt(
                project_id=project_id,
                source_content=content,
                direction=direction,
                has_logo=effective_logo is not None,
                user_id=user_id,
                edit_instructions=edit_instructions,
                previous_image_prompt=previous_image_prompt
            )

            if not prompt_result.get("success"):
                raise ValueError(prompt_result.get("error", "Failed to generate image prompt"))

            # We keep Claude's structural pass for the UI metadata —
            # topic_title, topic_summary, key_sections drive the
            # infographic detail panel's text. But the image prompt
            # itself uses the user's direction verbatim (with a compact
            # brand prefix) so GPT Image 2 renders what the user
            # actually asked for, not Claude's paraphrase.
            topic_title = prompt_result.get("topic_title", "Infographic")
            topic_summary = prompt_result.get("topic_summary", "")
            key_sections = prompt_result.get("key_sections", [])

            image_brand_prefix = brand_context_loader.build_image_prompt_prefix(
                user_id, "infographic"
            )
            user_image_text = (direction or topic_title or "").strip()
            image_prompt = (
                f"{image_brand_prefix} {user_image_text}".strip()
                if image_brand_prefix else user_image_text
            )
            if not image_prompt:
                # Fall back to Claude's prompt if the user gave no
                # direction at all and Claude couldn't infer a title.
                image_prompt = prompt_result.get("image_prompt", "")

            # Step 2: Generate image with Gemini
            studio_index_service.update_infographic_job(
                project_id, job_id,
                progress="Generating infographic image..."
            )

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            on_partial = make_partial_callback(
                project_id=project_id,
                job_id=job_id,
                storage_kind="infographics",
                filename_builder=lambda idx, ts=timestamp: f"partial_{idx}_{ts}.png",
                url_builder=lambda fn, pid=project_id, jid=job_id: (
                    f"/api/v1/projects/{pid}/studio/infographics/{jid}/{fn}"
                ),
            )

            # Use multimodal method if logo is available (same pattern as social posts)
            if effective_logo:
                enhanced_prompt = (
                    "Create an infographic image that naturally incorporates "
                    "the provided brand logo/icon into the design. " + image_prompt
                )
                image_result = imagen_service.generate_image_with_reference(
                    prompt=enhanced_prompt,
                    reference_image_bytes=effective_logo,
                    reference_mime_type=logo_mime_type,
                    filename_prefix=f"infographic_{job_id[:8]}_{timestamp}",
                    aspect_ratio=INFOGRAPHIC_ASPECT_RATIO,
                    project_id=project_id,
                    on_partial=on_partial,
                )
            else:
                image_result = imagen_service.generate_image_bytes(
                    prompt=image_prompt,
                    filename_prefix=f"infographic_{job_id[:8]}_{timestamp}",
                    aspect_ratio=INFOGRAPHIC_ASPECT_RATIO,
                    project_id=project_id,
                    on_partial=on_partial,
                )

            if not image_result.get("success"):
                raise ValueError(image_result.get("error", "Failed to generate image"))

            # Upload image bytes to Supabase Storage
            image_bytes = image_result["image_bytes"]
            filename = image_result["filename"]

            storage_path = storage_service.upload_studio_binary(
                project_id, "infographics", job_id, filename, image_bytes, "image/png"
            )
            if not storage_path:
                raise ValueError("Failed to upload infographic image to storage")

            image_info = {
                "filename": filename,
                "content_type": "image/png",
                "size_bytes": len(image_bytes)
            }
            image_url = f"/api/v1/projects/{project_id}/studio/infographics/{job_id}/{filename}"

            # Calculate generation time
            duration = (datetime.now() - started_at).total_seconds()

            # Update job as complete
            studio_index_service.update_infographic_job(
                project_id, job_id,
                status="ready",
                progress="Complete",
                topic_title=topic_title,
                topic_summary=topic_summary,
                key_sections=key_sections,
                image=image_info,
                image_url=image_url,
                image_prompt=image_prompt,
                generation_time_seconds=round(duration, 1),
                completed_at=datetime.now().isoformat()
            )

            logger.info("Generated infographic in %.1fs", duration)

            return {
                "success": True,
                "job_id": job_id,
                "topic_title": topic_title,
                "topic_summary": topic_summary,
                "key_sections": key_sections,
                "image": image_info,
                "image_url": image_url,
                "duration_seconds": duration,
                "usage": prompt_result.get("usage", {})
            }

        except Exception as e:
            logger.exception("Infographic generation failed")
            studio_index_service.update_infographic_job(
                project_id, job_id,
                status="error",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_image_prompt(
        self,
        project_id: str,
        source_content: str,
        direction: str,
        has_logo: bool = False,
        user_id: Optional[str] = None,
        edit_instructions: Optional[str] = None,
        previous_image_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate infographic image prompt using Claude.

        Educational Note: Claude analyzes the source content and creates
        a detailed image prompt describing the visual layout, sections,
        icons, and color scheme for the infographic.

        When editing, the previous image prompt is provided as context
        so Claude can refine it based on the user's edit instructions.
        """
        config = self._load_config()

        # Build source section — include source content block only if available
        if source_content:
            source_section = (
                "=== SOURCE CONTENT ===\n"
                f"{source_content[:15000]}\n"
                "=== END SOURCE CONTENT ==="
            )
        else:
            source_section = "(No source document provided — generate the infographic based on the direction below.)"

        # Logo context — tells Claude to write prompts that reference the logo
        logo_context = ""
        if has_logo:
            logo_context = (
                "\nNOTE: A brand logo/icon will be provided to the image generator. "
                "Write image prompts that describe incorporating it naturally into "
                "the design — mention logo placement (top-left corner, header area) "
                "and how design elements should complement it."
            )

        # Edit context — provides previous prompt + edit instructions for refinement
        edit_context = ""
        if previous_image_prompt and edit_instructions:
            edit_context = (
                "\n\n=== EDIT MODE ===\n"
                "You are REFINING a previously generated infographic. "
                "The user wants changes to the existing design.\n\n"
                f"PREVIOUS IMAGE PROMPT:\n{previous_image_prompt}\n\n"
                f"USER'S EDIT INSTRUCTIONS:\n{edit_instructions}\n\n"
                "Apply the user's requested changes while keeping the rest of the "
                "infographic design intact. Return the FULL updated JSON response "
                "(not just the changes).\n"
                "=== END EDIT MODE ==="
            )

        # Build user message
        user_message = config["user_message"].format(
            source_section=source_section,
            direction=direction or "Create an informative infographic summarizing the key concepts.",
            logo_context=logo_context
        )

        # Append edit context after the formatted message
        if edit_context:
            user_message += edit_context

        messages = [{"role": "user", "content": user_message}]

        # Load brand context so Claude knows brand colors, voice, etc.
        brand_context = brand_context_loader.load_brand_context(
            project_id, "infographic", user_id=user_id
        )
        system_prompt = config["system_prompt"]
        if brand_context:
            system_prompt = f"{system_prompt}\n\n{brand_context}"

        try:
            response = claude_service.send_message(
                messages=messages,
                system_prompt=system_prompt,
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                project_id=project_id
            )

            # Extract text from response
            content_blocks = response.get("content_blocks", [])
            text_content = ""
            for block in content_blocks:
                if hasattr(block, "text"):
                    text_content = block.text
                    break
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_content = block.get("text", "")
                    break

            if not text_content:
                return {
                    "success": False,
                    "error": "No text response from Claude"
                }

            # Parse JSON from response
            json_start = text_content.find("{")
            json_end = text_content.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                return {
                    "success": False,
                    "error": "No JSON found in Claude response"
                }

            json_str = text_content[json_start:json_end]
            parsed = json.loads(json_str)

            return {
                "success": True,
                "topic_title": parsed.get("topic_title", "Infographic"),
                "topic_summary": parsed.get("topic_summary", ""),
                "key_sections": parsed.get("key_sections", []),
                "image_prompt": parsed.get("image_prompt", ""),
                "color_scheme": parsed.get("color_scheme", {}),
                "usage": response.get("usage", {})
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse Claude response as JSON: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate image prompt: {str(e)}"
            }


# Singleton instance
infographic_service = InfographicService()
