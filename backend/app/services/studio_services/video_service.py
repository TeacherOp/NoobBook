"""
Video Generation Service - Simple video generation using Google Veo 2.0.

Educational Note: This is a simple service (not an agent) that:
1. Uses Claude to generate an optimized video prompt from source content
2. Calls Google Veo API with the generated prompt
3. Saves videos and updates job status
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.integrations.google.video_service import google_video_service

logger = logging.getLogger(__name__)
from app.services.ai_services.video_prompt_service import video_prompt_service
from app.services.studio_services import studio_index_service
from app.services.integrations.supabase import storage_service


class VideoService:
    """
    Simple video generation service.

    Educational Note: Takes prompt + parameters, calls Google Veo API,
    saves videos, and updates job status. No agent loop needed.
    """

    def generate_video(
        self,
        project_id: str,
        job_id: str,
        source_id: str,
        direction: str = "",
        aspect_ratio: str = "16:9",
        duration_seconds: int = 8,
        number_of_videos: int = 1,
        edit_instructions: Optional[str] = None,
        previous_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate video(s) from source content.

        Args:
            project_id: Project ID
            job_id: Video job ID
            source_id: Source to generate from
            direction: User's direction/guidance
            aspect_ratio: "16:9" or "16:10"
            duration_seconds: 5-8 seconds
            number_of_videos: 1-4 videos
            edit_instructions: Instructions for editing (refining the prompt)
            previous_prompt: The generated prompt from the parent video

        Returns:
            Result dict with success status and video info
        """
        # Update job to processing
        studio_index_service.update_video_job(
            project_id, job_id,
            status="processing",
            status_message="Generating video prompt with Claude..."
        )

        # Step 1: Generate optimized video prompt using Claude
        prompt_result = video_prompt_service.generate_video_prompt(
            project_id=project_id,
            source_id=source_id,
            direction=direction,
            edit_instructions=edit_instructions,
            previous_prompt=previous_prompt
        )

        if not prompt_result["success"]:
            # Failed to generate prompt
            studio_index_service.update_video_job(
                project_id, job_id,
                status="error",
                error_message=f"Failed to generate video prompt: {prompt_result.get('error', 'Unknown error')}"
            )
            return prompt_result

        video_prompt = prompt_result["prompt"]

        # Update job with generated prompt
        studio_index_service.update_video_job(
            project_id, job_id,
            status_message="Generating video with Google Veo...",
            generated_prompt=video_prompt
        )

        # Progress callback
        def on_progress(message: str):
            studio_index_service.update_video_job(
                project_id, job_id,
                status_message=message
            )

        # Step 2: Generate video(s) using Google Veo (returns bytes)
        result = google_video_service.generate_video_bytes(
            prompt=video_prompt,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            number_of_videos=number_of_videos,
            on_progress=on_progress
        )

        if not result["success"]:
            # Update job to error
            studio_index_service.update_video_job(
                project_id, job_id,
                status="error",
                error_message=result.get("error", "Video generation failed")
            )
            return result

        # Upload videos to Supabase Storage
        videos = result["videos"]

        # Build video info for job
        video_info = []
        for video in videos:
            # Upload each video to Supabase Storage
            storage_path = storage_service.upload_studio_binary(
                project_id, "videos", job_id,
                video["filename"], video["video_bytes"], "video/mp4"
            )
            if not storage_path:
                logger.warning("Failed to upload video %s to storage", video["filename"])
                continue

            video_info.append({
                "filename": video["filename"],
                "uri": video["uri"],
                "preview_url": f"/api/v1/projects/{project_id}/studio/videos/{job_id}/preview/{video['filename']}",
                "download_url": f"/api/v1/projects/{project_id}/studio/videos/{job_id}/download/{video['filename']}"
            })

        studio_index_service.update_video_job(
            project_id, job_id,
            status="ready",
            status_message="Video generation complete!",
            videos=video_info,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            completed_at=datetime.now().isoformat()
        )

        return {
            "success": True,
            "job_id": job_id,
            "videos": video_info,
            "count": len(video_info)
        }


# Singleton instance
video_service = VideoService()
