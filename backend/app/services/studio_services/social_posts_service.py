"""
Social Posts Service - Generates social media posts with platform-specific images and copy.

Educational Note: This service implements a two-step AI pipeline:
1. Claude generates platform-specific copy and image prompts
2. Google Gemini generates images with correct aspect ratios for each platform

Platforms:
- LinkedIn: 16:9 (professional, landscape)
- Instagram/Facebook: 1:1 (square, engaging)
- Twitter/X: 16:9 (landscape, casual)

All images are stored in Supabase Storage.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service

logger = logging.getLogger(__name__)
from app.services.integrations.google.imagen_service import imagen_service
from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service
from app.services.studio_services.partial_image_utils import make_partial_callback
from app.config import prompt_loader, brand_context_loader


# Platform to Gemini aspect ratio mapping
PLATFORM_ASPECT_RATIOS = {
    "linkedin": "16:9",      # Professional landscape (1200x627 -> 16:9 is closest)
    "instagram": "1:1",      # Square for feed posts
    "twitter": "16:9",       # Landscape for engagement
}


class SocialPostsService:
    """
    Service for generating social media posts with images.

    Educational Note: This service orchestrates the full pipeline:
    1. Claude generates platform-specific copy and image prompts
    2. Gemini generates images with appropriate aspect ratios
    """

    def __init__(self):
        """Initialize service with lazy-loaded config."""
        self._prompt_config = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("social_posts")
        return self._prompt_config

    def generate_social_posts(
        self,
        project_id: str,
        job_id: str,
        topic: str,
        direction: str = "",
        platforms: List[str] | None = None,
        logo_image_bytes: Optional[bytes] = None,
        logo_mime_type: str = "image/png",
        user_id: Optional[str] = None,
        edit_instructions: Optional[str] = None,
        previous_posts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate social media posts for selected platforms.

        Educational Note: This is the main orchestrator that:
        1. Uses Claude to generate copy + image prompts per platform
        2. Uses Gemini to generate images with correct aspect ratios
        3. Updates job status throughout

        Args:
            project_id: The project UUID
            job_id: The job ID for status tracking
            topic: The topic/content to create posts about
            direction: Additional context/direction from the user
            platforms: List of platforms to generate for (default: all 3)
            logo_image_bytes: Optional brand logo/icon bytes to incorporate in images
            logo_mime_type: MIME type of the logo image

        Returns:
            Dict with success status, posts data, and metadata
        """
        if platforms is None:
            platforms = ["linkedin", "instagram", "twitter"]
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_social_post_job(
            project_id, job_id,
            status="processing",
            progress="Generating platform-specific content...",
            started_at=datetime.now().isoformat()
        )

        # Step 1: Generate copy and image prompts with Claude
        content_result = self._generate_content(
            project_id=project_id,
            topic=topic,
            direction=direction,
            job_id=job_id,
            platforms=platforms,
            has_logo=logo_image_bytes is not None,
            user_id=user_id,
            edit_instructions=edit_instructions,
            previous_posts=previous_posts
        )

        if not content_result.get("success"):
            studio_index_service.update_social_post_job(
                project_id, job_id,
                status="error",
                error=content_result.get("error", "Failed to generate content"),
                completed_at=datetime.now().isoformat()
            )
            return content_result

        posts_data = content_result.get("posts", [])
        topic_summary = content_result.get("topic_summary", "")

        # Safety filter: only keep posts for requested platforms
        posts_data = [p for p in posts_data if p.get("platform", "").lower() in platforms]

        # Update progress
        studio_index_service.update_social_post_job(
            project_id, job_id,
            progress="Generating images..."
        )

        # The image prompt is the user's chat direction with a compact
        # brand prefix prepended. Claude still writes captions and
        # hashtags per platform (those benefit from the platform-specific
        # voice), but image generation goes directly off the user's
        # words. Same prompt for every platform — only the aspect ratio
        # differs.
        image_brand_prefix = brand_context_loader.build_image_prompt_prefix(
            user_id, "social"
        )
        image_user_text = (direction or topic or "").strip()
        shared_image_prompt = (
            f"{image_brand_prefix} {image_user_text}".strip()
            if image_brand_prefix else image_user_text
        )

        # Step 2: Generate images for each platform and upload to Supabase
        all_posts = []

        for i, post_data in enumerate(posts_data):
            platform = post_data.get("platform", f"platform_{i+1}")
            image_prompt = shared_image_prompt
            aspect_ratio = PLATFORM_ASPECT_RATIOS.get(platform, "1:1")

            if not image_prompt:
                continue

            # Update progress
            studio_index_service.update_social_post_job(
                project_id, job_id,
                progress=f"Generating {platform} image ({i+1}/{len(posts_data)})..."
            )

            post_info = {
                "platform": platform,
                "copy": post_data.get("copy", ""),
                "hashtags": post_data.get("hashtags", []),
                "aspect_ratio": post_data.get("aspect_ratio", aspect_ratio),
                "image_prompt": image_prompt,
                "image": None,
                "image_url": None,
                "storage_path": None
            }

            _safe_platform = "".join(c if c.isalnum() else "_" for c in str(platform))
            on_partial = make_partial_callback(
                project_id=project_id,
                job_id=job_id,
                storage_kind="social_posts",
                filename_builder=lambda idx, p=_safe_platform: f"partial_{p}_{idx}.png",
                url_builder=lambda fn, pid=project_id, jid=job_id: (
                    f"/api/v1/projects/{pid}/studio/social/{jid}/{fn}"
                ),
            )

            # Generate image — use multimodal method if logo is available
            if logo_image_bytes:
                enhanced_prompt = (
                    "Create a social media post image that naturally incorporates "
                    "the provided brand logo/icon into the design. " + image_prompt
                )
                result = imagen_service.generate_image_with_reference(
                    prompt=enhanced_prompt,
                    reference_image_bytes=logo_image_bytes,
                    reference_mime_type=logo_mime_type,
                    filename_prefix=f"social_{job_id[:8]}_{platform}",
                    aspect_ratio=aspect_ratio,
                    project_id=project_id,
                    on_partial=on_partial,
                )
            else:
                result = imagen_service.generate_image_bytes(
                    prompt=image_prompt,
                    filename_prefix=f"social_{job_id[:8]}_{platform}",
                    aspect_ratio=aspect_ratio,
                    project_id=project_id,
                    on_partial=on_partial,
                )

            if result.get("success"):
                filename = result["filename"]
                image_bytes = result["image_bytes"]
                content_type = result["content_type"]

                # Upload to Supabase Storage
                storage_path = storage_service.upload_studio_binary(
                    project_id=project_id,
                    job_type="social_posts",
                    job_id=job_id,
                    filename=filename,
                    file_data=image_bytes,
                    content_type=content_type
                )

                if storage_path:
                    # Use backend API path instead of Supabase internal URL
                    # (Supabase runs on Docker-internal hostname, not accessible from browser)
                    api_path = f"/api/v1/projects/{project_id}/studio/social/{job_id}/{filename}"
                    post_info["image"] = {"filename": filename}
                    post_info["image_url"] = api_path
                    post_info["storage_path"] = storage_path

            all_posts.append(post_info)

        if not all_posts:
            studio_index_service.update_social_post_job(
                project_id, job_id,
                status="error",
                error="No posts were generated",
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": "No posts were generated"
            }

        # Count successful image generations
        posts_with_images = [p for p in all_posts if p.get("image")]

        # Step 3: Update job as complete
        duration = (datetime.now() - started_at).total_seconds()

        studio_index_service.update_social_post_job(
            project_id, job_id,
            status="ready",
            progress="Complete",
            posts=all_posts,
            topic_summary=topic_summary,
            post_count=len(all_posts),
            generation_time_seconds=duration,
            completed_at=datetime.now().isoformat()
        )

        logger.info("Generated %s/%s social posts with images in %.1fs", len(posts_with_images), len(all_posts), duration)

        return {
            "success": True,
            "job_id": job_id,
            "topic": topic,
            "posts": all_posts,
            "topic_summary": topic_summary,
            "count": len(all_posts),
            "duration_seconds": duration,
            "usage": content_result.get("usage", {})
        }

    def _generate_content(
        self,
        project_id: str,
        topic: str,
        direction: str,
        job_id: str,
        platforms: List[str] | None = None,
        has_logo: bool = False,
        user_id: Optional[str] = None,
        edit_instructions: Optional[str] = None,
        previous_posts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate social media content using Claude.

        Educational Note: Claude creates platform-specific copy and image prompts
        tailored to each platform's style, tone, and image dimensions.
        When a brand logo is available, Claude is instructed to write image prompts
        that describe incorporating the logo into the design.

        When editing, the previous posts data is provided as context
        so Claude can refine copy, hashtags, and image prompts based on
        the user's edit instructions.
        """
        if platforms is None:
            platforms = ["linkedin", "instagram", "twitter"]

        config = self._load_config()

        # Format platform names for the prompt (e.g., "LinkedIn, Instagram, and Twitter")
        platform_display = {
            "linkedin": "LinkedIn",
            "instagram": "Instagram",
            "twitter": "Twitter",
        }
        platform_names = [platform_display.get(p, p) for p in platforms]
        if len(platform_names) > 1:
            platforms_str = ", ".join(platform_names[:-1]) + " and " + platform_names[-1]
        else:
            platforms_str = platform_names[0]

        # Logo context — tells Claude to write prompts that reference the logo
        logo_context = ""
        if has_logo:
            logo_context = (
                "\nNOTE: A brand logo/icon will be provided to the image generator. "
                "Write image prompts that describe incorporating it naturally into "
                "the design — mention logo placement (corner, centered, as part of "
                "the composition) and how design elements should complement it."
            )

        # Edit context — provides previous posts + edit instructions for refinement
        edit_context = ""
        if previous_posts and edit_instructions:
            # Serialize previous posts for Claude to reference
            previous_posts_summary = json.dumps(
                [{
                    "platform": p.get("platform"),
                    "copy": p.get("copy"),
                    "hashtags": p.get("hashtags"),
                    "image_prompt": p.get("image_prompt")
                } for p in previous_posts],
                indent=2
            )
            edit_context = (
                "\n\n=== EDIT MODE ===\n"
                "You are REFINING previously generated social posts. "
                "The user wants changes to the existing content.\n\n"
                f"PREVIOUS POSTS:\n{previous_posts_summary}\n\n"
                f"USER'S EDIT INSTRUCTIONS:\n{edit_instructions}\n\n"
                "Apply the user's requested changes while keeping the rest "
                "intact. You can modify copy, hashtags, AND/OR image prompts "
                "as needed. Return the FULL updated JSON response (not just "
                "the changes).\n"
                "=== END EDIT MODE ==="
            )

        # Build user message
        user_message = config["user_message"].format(
            topic=topic,
            direction=direction or "Create engaging social media posts for this topic.",
            platforms=platforms_str,
            logo_context=logo_context
        )

        # Append edit context after the formatted message
        if edit_context:
            user_message += edit_context

        messages = [{"role": "user", "content": user_message}]

        # Load brand context so Claude knows brand name, colors, voice, etc.
        brand_context = brand_context_loader.load_brand_context(
            project_id, "social_post", user_id=user_id
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
            # Find JSON in the response (might be wrapped in markdown code blocks)
            json_start = text_content.find("{")
            json_end = text_content.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                return {
                    "success": False,
                    "error": "No JSON found in Claude response"
                }

            json_str = text_content[json_start:json_end]
            parsed = json.loads(json_str)
            posts = parsed.get("posts", [])
            topic_summary = parsed.get("topic_summary", "")

            return {
                "success": True,
                "posts": posts,
                "topic_summary": topic_summary,
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
                "error": f"Failed to generate content: {str(e)}"
            }


# Singleton instance
social_posts_service = SocialPostsService()
