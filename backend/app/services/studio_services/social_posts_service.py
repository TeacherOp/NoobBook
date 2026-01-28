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
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.integrations.google.imagen_service import imagen_service
from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service
from app.config import prompt_loader


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
        direction: str = ""
    ) -> Dict[str, Any]:
        """
        Generate social media posts for multiple platforms.

        Educational Note: This is the main orchestrator that:
        1. Uses Claude to generate copy + image prompts per platform
        2. Uses Gemini to generate images with correct aspect ratios
        3. Updates job status throughout

        Args:
            project_id: The project UUID
            job_id: The job ID for status tracking
            topic: The topic/content to create posts about
            direction: Additional context/direction from the user

        Returns:
            Dict with success status, posts data, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_social_post_job(
            project_id, job_id,
            status="processing",
            progress="Generating platform-specific content...",
            started_at=datetime.now().isoformat()
        )

        print(f"[SocialPosts] Starting job {job_id}")
        print(f"  Topic: {topic}")

        # Step 1: Generate copy and image prompts with Claude
        content_result = self._generate_content(
            project_id=project_id,
            topic=topic,
            direction=direction,
            job_id=job_id
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
        print(f"  Generated content for {len(posts_data)} platforms")

        # Update progress
        studio_index_service.update_social_post_job(
            project_id, job_id,
            progress="Generating images..."
        )

        # Step 2: Generate images for each platform and upload to Supabase
        all_posts = []

        for i, post_data in enumerate(posts_data):
            platform = post_data.get("platform", f"platform_{i+1}")
            image_prompt = post_data.get("image_prompt", "")
            aspect_ratio = PLATFORM_ASPECT_RATIOS.get(platform, "1:1")

            if not image_prompt:
                continue

            print(f"  Generating {platform} image (aspect ratio: {aspect_ratio})...")

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

            # Generate image and get bytes (not saved to disk)
            result = imagen_service.generate_image_bytes(
                prompt=image_prompt,
                filename_prefix=f"social_{job_id[:8]}_{platform}",
                aspect_ratio=aspect_ratio
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
                    # Get public URL
                    public_url = storage_service.get_studio_public_url(
                        project_id=project_id,
                        job_type="social_posts",
                        job_id=job_id,
                        filename=filename
                    )
                    post_info["image"] = {"filename": filename}
                    post_info["image_url"] = public_url
                    post_info["storage_path"] = storage_path
                    print(f"    Uploaded: {filename}")

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

        print(f"  Generated {len(posts_with_images)}/{len(all_posts)} posts with images in {duration:.1f}s")

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
        job_id: str
    ) -> Dict[str, Any]:
        """
        Generate social media content using Claude.

        Educational Note: Claude creates platform-specific copy and image prompts
        tailored to each platform's style, tone, and image dimensions.
        """
        config = self._load_config()

        # Build user message
        user_message = config["user_message"].format(
            topic=topic,
            direction=direction or "Create engaging social media posts for this topic."
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
