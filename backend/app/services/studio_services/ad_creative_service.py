"""
Ad Creative Service - Generates ad creatives for Facebook/Instagram.

Educational Note: This service implements a two-step AI pipeline:
1. Claude Haiku generates optimized image prompts from product info
2. Google Gemini generates images from those prompts

Flow:
- Input: Product name + direction from chat signal
- Step 1: Haiku creates 3 image prompts (hero, lifestyle, aspirational)
- Step 2: Gemini generates images for each prompt
- Output: 3 ad creative images saved to disk
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)
from app.services.integrations.google.imagen_service import imagen_service
from app.services.studio_services import studio_index_service
from app.services.studio_services.partial_image_utils import make_partial_callback
from app.config import brand_context_loader
from app.services.integrations.supabase import storage_service


class AdCreativeService:
    """
    Service for generating ad creatives.

    The user's chat prompt (stored as the studio_signal `direction`) is
    sent verbatim to GPT Image 2 — once per variation, with a compact
    brand prefix prepended. We no longer ask Haiku to fan the prompt out
    into hero/lifestyle/aspirational angles; that step rephrased the
    user's intent and lost specifics.
    """

    def generate_ad_creatives(
        self,
        project_id: str,
        job_id: str,
        product_name: str,
        direction: str = "",
        logo_image_bytes: Optional[bytes] = None,
        logo_mime_type: str = "image/png",
        user_id: Optional[str] = None,
        previous_prompts: Optional[list] = None,
        edit_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ad creatives for a product.

        Educational Note: This is the main orchestrator that:
        1. Uses Haiku to generate image prompts
        2. Uses Gemini to generate images
        3. Updates job status throughout

        Args:
            project_id: The project UUID
            job_id: The job ID for status tracking
            product_name: Name of the product to create ads for
            direction: Additional context/direction from the user
            logo_image_bytes: Optional brand logo/icon bytes to incorporate in images
            logo_mime_type: MIME type of the logo image

        Returns:
            Dict with success status, image paths, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_ad_job(
            project_id, job_id,
            status="processing",
            progress="Preparing ad creative prompts...",
            started_at=datetime.now().isoformat()
        )

        # Step 1: Build image prompts from the user's direction directly.
        # We used to ask Haiku to fan the user prompt out into three
        # different angles (hero / lifestyle / aspirational), but that
        # introduced drift — the AI added style notes, color choices, and
        # framing the user never asked for. Now: same user prompt, three
        # variations from GPT Image 2's stochastic output, with a compact
        # brand block prepended so brand identity stays consistent.
        brand_prefix = brand_context_loader.build_image_prompt_prefix(
            user_id, "ads_creative"
        )
        user_direction = (direction or product_name or "").strip()
        if not user_direction:
            studio_index_service.update_ad_job(
                project_id, job_id,
                status="error",
                error="No direction provided for the ad",
                completed_at=datetime.now().isoformat()
            )
            return {"success": False, "error": "No direction provided for the ad"}

        final_prompt = (
            f"{brand_prefix} {user_direction}".strip() if brand_prefix else user_direction
        )
        prompts = [
            {"type": f"variation_{i+1}", "prompt": final_prompt}
            for i in range(3)
        ]

        # Update progress
        studio_index_service.update_ad_job(
            project_id, job_id,
            progress="Generating images..."
        )

        # Step 2: Generate images with Gemini
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        all_images = []

        for i, prompt_data in enumerate(prompts):
            prompt_type = prompt_data.get("type", f"image_{i+1}")
            prompt_text = prompt_data.get("prompt", "")

            if not prompt_text:
                continue

            # Update progress
            studio_index_service.update_ad_job(
                project_id, job_id,
                progress=f"Generating {prompt_type} image ({i+1}/{len(prompts)})..."
            )

            _safe_type = "".join(c if c.isalnum() else "_" for c in prompt_type)
            on_partial = make_partial_callback(
                project_id=project_id,
                job_id=job_id,
                storage_kind="creatives",
                filename_builder=lambda idx, t=_safe_type, ts=timestamp: f"partial_{t}_{idx}_{ts}.png",
                url_builder=lambda fn, pid=project_id, jid=job_id: (
                    f"/api/v1/projects/{pid}/studio/creatives/{jid}/{fn}"
                ),
            )

            # Generate image — use multimodal method if logo is available
            if logo_image_bytes:
                enhanced_prompt = (
                    "Create an ad creative image that naturally incorporates "
                    "the provided brand logo/icon into the design. " + prompt_text
                )
                result = imagen_service.generate_image_with_reference(
                    prompt=enhanced_prompt,
                    reference_image_bytes=logo_image_bytes,
                    reference_mime_type=logo_mime_type,
                    filename_prefix=f"ad_{job_id[:8]}_{prompt_type}_{timestamp}",
                    project_id=project_id,
                    on_partial=on_partial,
                )
            else:
                result = imagen_service.generate_image_bytes(
                    prompt=prompt_text,
                    filename_prefix=f"ad_{job_id[:8]}_{prompt_type}_{timestamp}",
                    project_id=project_id,
                    on_partial=on_partial,
                )

            if result.get("success"):
                image_bytes = result["image_bytes"]
                filename = result["filename"]

                # Upload to Supabase Storage
                storage_path = storage_service.upload_studio_binary(
                    project_id, "creatives", job_id, filename, image_bytes, "image/png"
                )
                if storage_path:
                    image_info = {
                        "filename": filename,
                        "content_type": "image/png",
                        "size_bytes": len(image_bytes),
                        "type": prompt_type,
                        "prompt": prompt_text
                    }
                    all_images.append(image_info)

        if not all_images:
            studio_index_service.update_ad_job(
                project_id, job_id,
                status="error",
                error="No images were generated",
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": "No images were generated"
            }

        # Step 3: Update job as complete
        duration = (datetime.now() - started_at).total_seconds()

        # Build image URLs (include job_id for Supabase storage path)
        for img in all_images:
            img["url"] = f"/api/v1/projects/{project_id}/studio/creatives/{job_id}/{img['filename']}"

        studio_index_service.update_ad_job(
            project_id, job_id,
            status="ready",
            progress="Complete",
            images=all_images,
            completed_at=datetime.now().isoformat()
        )

        logger.info("Generated %s ad images in %.1fs", len(all_images), duration)

        return {
            "success": True,
            "job_id": job_id,
            "product_name": product_name,
            "images": all_images,
            "count": len(all_images),
            "duration_seconds": duration,
            "usage": {},
        }


# Singleton instance
ad_creative_service = AdCreativeService()
