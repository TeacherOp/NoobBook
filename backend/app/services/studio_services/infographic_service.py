"""
Infographic Service - Generates visual infographics from source content.

Educational Note: This service implements a two-step AI pipeline:
1. Claude analyzes source content and creates a detailed image prompt
2. Google Gemini generates the infographic image

Infographics are visual summaries that organize information in an
educational, easy-to-scan format with icons, sections, and visual flow.
"""
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.integrations.google.imagen_service import imagen_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.config import prompt_loader
from app.services.integrations.supabase import storage_service
from app.utils.path_utils import get_studio_dir


# Infographic aspect ratio - landscape for modal display
INFOGRAPHIC_ASPECT_RATIO = "16:9"


def get_studio_infographics_dir(project_id: str) -> Path:
    """Get the directory for infographic images."""
    studio_dir = get_studio_dir(project_id)
    infographics_dir = studio_dir / "infographics"
    infographics_dir.mkdir(parents=True, exist_ok=True)
    return infographics_dir


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
        direction: str = ""
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

        print(f"[Infographic] Starting job {job_id}")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")
            print(f"  Source: {source_name}")

            # Get source content
            content = self._get_source_content(project_id, source_id)
            if not content:
                raise ValueError("No content found for source")

            # Step 1: Generate image prompt with Claude
            studio_index_service.update_infographic_job(
                project_id, job_id,
                progress="Designing infographic layout..."
            )

            prompt_result = self._generate_image_prompt(
                project_id=project_id,
                source_content=content,
                direction=direction
            )

            if not prompt_result.get("success"):
                raise ValueError(prompt_result.get("error", "Failed to generate image prompt"))

            image_prompt = prompt_result.get("image_prompt", "")
            topic_title = prompt_result.get("topic_title", "Infographic")
            topic_summary = prompt_result.get("topic_summary", "")
            key_sections = prompt_result.get("key_sections", [])

            print(f"  Topic: {topic_title}")
            print(f"  Sections: {len(key_sections)}")

            # Step 2: Generate image with Gemini
            studio_index_service.update_infographic_job(
                project_id, job_id,
                progress="Generating infographic image..."
            )

            infographics_dir = get_studio_infographics_dir(project_id)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            image_result = imagen_service.generate_images(
                prompt=image_prompt,
                output_dir=infographics_dir,
                num_images=1,
                filename_prefix=f"infographic_{job_id[:8]}_{timestamp}",
                aspect_ratio=INFOGRAPHIC_ASPECT_RATIO
            )

            if not image_result.get("success") or not image_result.get("images"):
                raise ValueError(image_result.get("error", "Failed to generate image"))

            image_info = image_result["images"][0]
            image_url = f"/api/v1/projects/{project_id}/studio/infographics/{image_info['filename']}"

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

            print(f"  Generated infographic in {duration:.1f}s")

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
            print(f"[Infographic] Error: {e}")
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
        direction: str
    ) -> Dict[str, Any]:
        """
        Generate infographic image prompt using Claude.

        Educational Note: Claude analyzes the source content and creates
        a detailed image prompt describing the visual layout, sections,
        icons, and color scheme for the infographic.
        """
        config = self._load_config()

        # Build user message
        user_message = config["user_message"].format(
            source_content=source_content[:15000],  # Limit content
            direction=direction or "Create an informative infographic summarizing the key concepts."
        )

        messages = [{"role": "user", "content": user_message}]

        try:
            response = claude_service.send_message(
                messages=messages,
                system_prompt=config["system_prompt"],
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
