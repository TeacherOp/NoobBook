"""
Google Imagen Service - Image generation using Gemini Pro Image model.

Educational Note: This service uses Google's Gemini 3 Pro Image model
to generate images from text prompts. It's used for ad creative generation.

The gemini-3-pro-image-preview model uses generate_content API with
GenerateContentConfig and ImageConfig for aspect ratio and resolution control.

Images are returned as bytes for direct upload to Supabase Storage.
"""
import os
import io
import tempfile
from typing import Dict, Any, List
from datetime import datetime


class ImagenService:
    """
    Service class for image generation via Gemini Pro Image API.

    Educational Note: Uses generate_content with gemini-3-pro-image-preview model.
    Requires GenerateContentConfig with response_modalities=['TEXT', 'IMAGE']
    and ImageConfig for aspect ratio and resolution settings.
    """

    MODEL_ID = "gemini-3-pro-image-preview"
    DEFAULT_ASPECT_RATIO = "9:16"  # Mobile-first for Facebook/Instagram Stories & Reels
    DEFAULT_RESOLUTION = "1K"  # Options: 1K, 2K, 4K

    def __init__(self):
        """Initialize the Imagen service."""
        self._client = None

    def _get_client(self):
        """
        Get or create the Google GenAI client.

        Returns:
            Google GenAI client instance

        Raises:
            ValueError: If GEMINI_API_KEY is not configured
        """
        if self._client is None:
            api_key = os.getenv('NANO_BANANA_API_KEY')
            if not api_key:
                raise ValueError(
                    "NANO_BANANA_API_KEY not found in environment. "
                    "Please configure it in App Settings."
                )

            from google import genai
            self._client = genai.Client(api_key=api_key)

        return self._client

    def _get_types(self):
        """Get the google.genai.types module for config objects."""
        from google.genai import types
        return types

    def generate_images(
        self,
        prompt: str,
        output_dir: Path,
        num_images: int = 3,
        filename_prefix: str = "creative",
        aspect_ratio: str = None,
        resolution: str = None
    ) -> Dict[str, Any]:
        """
        Generate images from a text prompt.

        Educational Note: This method calls Gemini 3 Pro Image API with
        GenerateContentConfig for response_modalities and ImageConfig
        for aspect ratio and resolution control.

        Args:
            prompt: The text prompt describing the image to generate
            output_dir: Directory to save generated images
            num_images: Number of images to generate (max 3)
            filename_prefix: Prefix for generated image filenames
            aspect_ratio: Image aspect ratio (1:1, 16:9, etc.)
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Dict with success status, image paths, and metadata
        """
        if not prompt or not prompt.strip():
            return {
                "success": False,
                "error": "No prompt provided for image generation"
            }

        # Limit to 3 images for demo
        num_images = min(num_images, 3)

        # Use defaults if not specified
        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO
        resolution = resolution or self.DEFAULT_RESOLUTION

        try:
            client = self._get_client()
            types = self._get_types()

            print(f"[Imagen] Generating {num_images} images...")
            print(f"  Model: {self.MODEL_ID}")
            print(f"  Aspect ratio: {aspect_ratio}, Resolution: {resolution}")
            print(f"  Prompt: {prompt[:100]}...")

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            image_paths = []
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Generate images one by one
            for i in range(num_images):
                print(f"  Generating image {i+1}/{num_images}...")

                # Use the new API format with GenerateContentConfig and ImageConfig
                response = client.models.generate_content(
                    model=self.MODEL_ID,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE'],
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                            image_size=resolution
                        ),
                    )
                )

                # Extract image from response parts
                for part in response.parts:
                    if part.text is not None:
                        # Log any text response from the model
                        print(f"    Model text: {part.text[:100]}...")
                    elif (image := part.as_image()):
                        filename = f"{filename_prefix}_{timestamp}_{i+1}.png"
                        filepath = output_dir / filename
                        image.save(str(filepath))
                        image_paths.append({
                            "filename": filename,
                            "path": str(filepath),
                            "index": i + 1
                        })
                        print(f"    Saved: {filename}")
                        break  # Got the image, move to next

            if not image_paths:
                return {
                    "success": False,
                    "error": "No images generated by the API"
                }

            return {
                "success": True,
                "images": image_paths,
                "count": len(image_paths),
                "prompt": prompt,
                "model": self.MODEL_ID,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "generated_at": datetime.now().isoformat()
            }

        except ValueError as e:
            # API key not configured
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            print(f"[Imagen] Error generating images: {e}")
            return {
                "success": False,
                "error": f"Image generation failed: {str(e)}"
            }

    def generate_image_bytes(
        self,
        prompt: str,
        filename_prefix: str = "image",
        aspect_ratio: str = None,
        resolution: str = None
    ) -> Dict[str, Any]:
        """
        Generate a single image and return as bytes (for Supabase upload).

        Educational Note: This method generates one image and returns the raw
        bytes instead of saving to disk. The caller is responsible for uploading
        to Supabase Storage.

        Args:
            prompt: The text prompt describing the image to generate
            filename_prefix: Prefix for the filename
            aspect_ratio: Image aspect ratio (1:1, 16:9, etc.)
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Dict with success status and image bytes:
            {
                "success": True,
                "filename": "prefix_timestamp.png",
                "image_bytes": bytes,
                "content_type": "image/png"
            }
        """
        if not prompt or not prompt.strip():
            return {
                "success": False,
                "error": "No prompt provided for image generation"
            }

        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO
        resolution = resolution or self.DEFAULT_RESOLUTION

        try:
            client = self._get_client()
            types = self._get_types()

            print(f"[Imagen] Generating image...")
            print(f"  Aspect ratio: {aspect_ratio}, Resolution: {resolution}")
            print(f"  Prompt: {prompt[:100]}...")

            response = client.models.generate_content(
                model=self.MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=resolution
                    ),
                )
            )

            # Extract image from response
            for part in response.parts:
                if part.text is not None:
                    print(f"    Model text: {part.text[:100]}...")
                elif (image := part.as_image()):
                    # Google GenAI Image uses .save(filepath), not .save(buffer, format)
                    # So we save to a temp file and read the bytes
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name

                    try:
                        image.save(tmp_path)
                        with open(tmp_path, 'rb') as f:
                            img_bytes = f.read()
                    finally:
                        # Clean up temp file
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{filename_prefix}_{timestamp}.png"

                    print(f"    Generated: {filename} ({len(img_bytes)} bytes)")

                    return {
                        "success": True,
                        "filename": filename,
                        "image_bytes": img_bytes,
                        "content_type": "image/png"
                    }

            return {
                "success": False,
                "error": "No image generated by the API"
            }

        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            print(f"[Imagen] Error generating image: {e}")
            return {"success": False, "error": f"Image generation failed: {str(e)}"}

    def is_configured(self) -> bool:
        """
        Check if Gemini API key is configured.

        Returns:
            True if API key is set, False otherwise
        """
        return bool(os.getenv('NANO_BANANA_API_KEY'))


# Singleton instance
imagen_service = ImagenService()
