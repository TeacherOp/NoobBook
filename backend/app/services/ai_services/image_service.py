"""
Image Service - Manages image processing and content extraction using tool-based approach.

Educational Note: This service extracts comprehensive content from images using Claude's
vision capabilities. It uses a tool-based approach similar to PDF extraction:
- Images are sent as base64-encoded content blocks
- Claude analyzes the image and calls submit_image_extraction tool
- The tool returns structured data about the image content
- Results are saved as text files for use in chat context

Supported formats: JPEG, PNG, GIF, WebP (max 5MB each per API constraint)
"""
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.background_services import task_service
from app.config import tool_loader, prompt_loader, get_anthropic_config
from app.utils import claude_parsing_utils
from app.utils.encoding_utils import encode_file_to_base64, get_media_type
from app.utils.rate_limit_utils import RateLimiter
from app.utils.text import build_processed_output
from app.utils.embedding_utils import count_tokens


class ImageService:
    """
    Service class for extracting content from images using Claude's vision.

    Educational Note: This service handles image analysis:
    1. Reads image file and encodes to base64
    2. Sends to Claude with submit_image_extraction tool
    3. Parses structured response (subject, text, visuals, data, etc.)
    4. Saves combined content as text file for chat context
    """

    def __init__(self):
        """Initialize the image service."""
        self._tool_definition = None

    def _load_tool_definition(self) -> Dict[str, Any]:
        """Load the image extraction tool definition."""
        if self._tool_definition is None:
            self._tool_definition = tool_loader.load_tool("image_tools", "image_extraction")
        return self._tool_definition

    def _parse_tool_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse image extraction tool response from Claude.

        Educational Note: Uses claude_parsing_utils for generic tool parsing,
        then extracts image-specific fields.
        """
        tool_inputs = claude_parsing_utils.extract_tool_inputs(response, "submit_image_extraction")

        if not tool_inputs:
            return {
                "success": False,
                "error": "No tool call received from Claude"
            }

        inputs = tool_inputs[0]
        return {
            "success": True,
            "subject": inputs.get("subject", ""),
            "content_type": inputs.get("content_type", "other"),
            "text_content": inputs.get("text_content", "[NO TEXT]"),
            "visual_description": inputs.get("visual_description", ""),
            "colors_and_style": inputs.get("colors_and_style", ""),
            "data_content": inputs.get("data_content", "[NO DATA]"),
            "summary": inputs.get("summary", "")
        }

    def _format_extraction_content(
        self,
        extraction: Dict[str, Any]
    ) -> str:
        """
        Format extracted image data as page content.

        Educational Note: Returns just the content (no header). The header
        and page markers are added by build_processed_output.
        """
        lines = [
            "## Subject",
            extraction.get("subject", ""),
            "",
            "## Text Content",
            extraction.get("text_content", "[NO TEXT]"),
            "",
            "## Visual Description",
            extraction.get("visual_description", ""),
            "",
            "## Colors and Style",
            extraction.get("colors_and_style", ""),
            "",
            "## Data Content",
            extraction.get("data_content", "[NO DATA]"),
            "",
            "## Summary",
            extraction.get("summary", ""),
        ]
        return "\n".join(lines)

    def extract_content_from_image(
        self,
        project_id: str,
        source_id: str,
        image_path: Path
    ) -> Dict[str, Any]:
        """
        Extract content from a single image file.

        Educational Note: This is the main entry point for image processing.
        1. Loads image and encodes to base64
        2. Sends to Claude with image content block
        3. Forces tool use for structured extraction
        4. Saves result as text file

        Args:
            project_id: The project UUID
            source_id: The source UUID
            image_path: Path to the image file

        Returns:
            Dict with extraction results
        """
        print(f"Starting image extraction for source: {source_id}")

        try:
            # Load configurations using centralized loaders
            prompt_config = prompt_loader.get_prompt_config("image_extraction")
            tool_def = self._load_tool_definition()
            tier_config = get_anthropic_config()

            model = prompt_config.get("model", "claude-haiku-4-5-20251001")
            system_prompt = prompt_config.get("system_prompt", "")
            user_message = prompt_config.get("user_message", "")
            max_tokens = prompt_config.get("max_tokens", 4000)
            temperature = prompt_config.get("temperature", 0.2)

            # Create rate limiter for this extraction
            requests_per_minute = tier_config.get("pages_per_minute", 100)
            rate_limiter = RateLimiter(requests_per_minute)

            print(f"Using model: {model}")

            image_base64 = encode_file_to_base64(image_path)
            media_type = get_media_type(image_path)

            print(f"Image encoded: {image_path.name} ({media_type})")

            content_blocks = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64
                    }
                },
                {
                    "type": "text",
                    "text": user_message
                }
            ]

            messages = [{"role": "user", "content": content_blocks}]

            # Apply rate limiting before API call
            rate_limiter.wait_if_needed()

            response = claude_service.send_message(
                messages=messages,
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=[tool_def],
                tool_choice={"type": "tool", "name": "submit_image_extraction"},
                project_id=project_id
            )

            extraction = self._parse_tool_response(response)

            if not extraction.get("success"):
                raise Exception(extraction.get("error", "Extraction failed"))

            # Build page content (images are single "pages")
            page_content = self._format_extraction_content(extraction)
            pages = [page_content]

            # Calculate character and token counts
            character_count = len(page_content)
            token_count = count_tokens(page_content)

            # Build metadata for IMAGE type
            content_type = extraction.get("content_type", "other")
            metadata = {
                "model_used": model,
                "content_type": content_type,
                "character_count": character_count,
                "token_count": token_count
            }

            # Use centralized build_processed_output for consistent format
            processed_content = build_processed_output(
                pages=pages,
                source_type="IMAGE",
                source_name=image_path.name,
                metadata=metadata
            )

            print(f"Image extraction complete: {image_path.name}")

            # Return processed content for processor to upload to Supabase Storage
            return {
                "success": True,
                "status": "ready",
                "processed_content": processed_content,
                "character_count": character_count,
                "token_count": token_count,
                "content_type": content_type,
                "summary": extraction.get("summary"),
                "token_usage": response.get("usage", {}),
                "model_used": model,
                "extracted_at": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"Image extraction failed: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e)
            }

    def extract_content_from_images_batch(
        self,
        project_id: str,
        source_id: str,
        image_paths: List[Path]
    ) -> Dict[str, Any]:
        """
        Extract content from multiple images in a single source.

        Educational Note: When multiple images are uploaded together,
        we process each one and combine results into a single output file.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            image_paths: List of paths to image files

        Returns:
            Dict with extraction results for all images
        """
        print(f"Starting batch image extraction for {len(image_paths)} images")

        try:
            # Load configurations using centralized loaders
            prompt_config = prompt_loader.get_prompt_config("image_extraction")
            tool_def = self._load_tool_definition()
            tier_config = get_anthropic_config()

            model = prompt_config.get("model", "claude-haiku-4-5-20251001")
            system_prompt = prompt_config.get("system_prompt", "")
            max_tokens = prompt_config.get("max_tokens", 4000)
            temperature = prompt_config.get("temperature", 0.2)

            # Create rate limiter for batch processing
            requests_per_minute = tier_config.get("pages_per_minute", 100)
            rate_limiter = RateLimiter(requests_per_minute)

            all_extractions = []
            total_input_tokens = 0
            total_output_tokens = 0

            for idx, image_path in enumerate(image_paths, 1):
                if task_service.is_target_cancelled(source_id):
                    print(f"Processing cancelled for source {source_id}")
                    raise Exception("Processing cancelled by user")

                print(f"Processing image {idx}/{len(image_paths)}: {image_path.name}")

                image_base64 = encode_file_to_base64(image_path)
                media_type = get_media_type(image_path)

                user_message = prompt_config.get("user_message", "")

                content_blocks = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": user_message
                    }
                ]

                messages = [{"role": "user", "content": content_blocks}]

                # Apply rate limiting before each API call
                rate_limiter.wait_if_needed()

                response = claude_service.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=[tool_def],
                    tool_choice={"type": "tool", "name": "submit_image_extraction"},
                    project_id=project_id
                )

                extraction = self._parse_tool_response(response)
                extraction["image_name"] = image_path.name

                all_extractions.append(extraction)

                total_input_tokens += response.get("usage", {}).get("input_tokens", 0)
                total_output_tokens += response.get("usage", {}).get("output_tokens", 0)

            # Build pages list (one page per image)
            pages = []
            for extraction in all_extractions:
                page_content = self._format_extraction_content(extraction)
                # Add image name at the top of each page for context
                image_name = extraction.get("image_name", "unknown")
                full_page = f"# {image_name}\n\n{page_content}"
                pages.append(full_page)

            # Calculate character and token counts
            full_text = "\n".join(pages)
            character_count = len(full_text)
            token_count = count_tokens(full_text)

            # Build metadata for IMAGE type (batch)
            metadata = {
                "model_used": model,
                "content_type": "batch",
                "character_count": character_count,
                "token_count": token_count
            }

            # Use centralized build_processed_output for consistent format
            # Source name indicates this is a batch
            processed_content = build_processed_output(
                pages=pages,
                source_type="IMAGE",
                source_name=f"{len(image_paths)} images",
                metadata=metadata
            )

            print(f"Batch extraction complete: {len(image_paths)} images processed")

            # Return processed content for processor to upload to Supabase Storage
            return {
                "success": True,
                "status": "ready",
                "processed_content": processed_content,
                "images_processed": len(image_paths),
                "character_count": character_count,
                "token_count": token_count,
                "token_usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens
                },
                "model_used": model,
                "extracted_at": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"Batch image extraction failed: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e)
            }


# Singleton instance
image_service = ImageService()
