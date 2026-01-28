"""
PPTX Service - Manages PowerPoint presentation processing using LibreOffice and Claude vision.

Educational Note: This service processes PPTX files in three stages:
1. Convert PPTX to PDF using LibreOffice headless mode (via pptx_utils)
2. Extract PDF pages as base64 (reusing existing pdf_utils)
3. Send to Claude vision for slide analysis

The conversion approach allows us to leverage the existing PDF infrastructure
while providing presentation-specific prompts that understand slides, not documents.

Processing Flow:
    PPTX → PDF (LibreOffice) → base64 pages → Claude vision → extracted content
"""
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.integrations.claude import claude_service
from app.services.background_services import task_service
from app.config import tool_loader, prompt_loader, get_anthropic_config
from app.utils import claude_parsing_utils
from app.utils.batching_utils import create_batches, DEFAULT_BATCH_SIZE
from app.utils.encoding_utils import encode_bytes_to_base64
from app.utils.pdf_utils import get_page_count, get_all_page_bytes
from app.utils.pptx_utils import convert_pptx_to_pdf
from app.utils.rate_limit_utils import RateLimiter
from app.utils.text import build_processed_output
from app.utils.embedding_utils import count_tokens


class CancelledException(Exception):
    """Raised when processing is cancelled by user."""
    pass


class PPTXService:
    """
    Service class for processing PowerPoint presentations.

    Educational Note: This service orchestrates PPTX processing:
    1. Converts PPTX to PDF using LibreOffice headless (via pptx_utils)
    2. Splits PDF into batches of slides (max 5 per batch)
    3. Sends each batch to Claude API for visual analysis
    4. Claude uses submit_slide_extraction tool for each slide
    5. Collects results, writes to file in slide order
    """

    def __init__(self):
        """Initialize the PPTX service."""
        self._tool_definition = None

    def _load_tool_definition(self) -> Dict[str, Any]:
        """Load the slide extraction tool definition."""
        if self._tool_definition is None:
            self._tool_definition = tool_loader.load_tool("pptx_tools", "pptx_extraction")
        return self._tool_definition

    def extract_content_from_pptx(
        self,
        project_id: str,
        source_id: str,
        pptx_path: Path
    ) -> Dict[str, Any]:
        """
        Extract content from a PPTX file.

        Educational Note: This is the main entry point for PPTX processing.
        It orchestrates the full pipeline:
        1. Convert PPTX to PDF (via pptx_utils)
        2. Extract slides in batches
        3. Process with Claude vision
        4. Save extracted content

        Args:
            project_id: The project UUID
            source_id: The source UUID
            pptx_path: Path to the PPTX file

        Returns:
            Dict with success status, extracted content info, and any errors
        """
        # Create a temporary directory for the PDF
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                # Step 1: Convert PPTX to PDF (using utility function)
                pdf_path = convert_pptx_to_pdf(pptx_path, temp_path)

                # Step 2: Get slide count
                total_slides = get_page_count(pdf_path)
                print(f"Presentation has {total_slides} slides")

                if total_slides == 0:
                    return {
                        "success": False,
                        "error": "Presentation has no slides"
                    }

                # Step 3: Load configurations using centralized loaders
                prompt_config = prompt_loader.get_prompt_config("pptx_extraction")
                tool_def = self._load_tool_definition()
                tier_config = get_anthropic_config()
                max_workers = tier_config["max_workers"]

                # Calculate batches per minute for rate limiting
                pages_per_minute = tier_config["pages_per_minute"]
                batches_per_minute = max(1, pages_per_minute // DEFAULT_BATCH_SIZE)
                rate_limiter = RateLimiter(batches_per_minute)

                # Step 4: Extract all slide bytes and create batches
                print("Extracting slide bytes...")
                slide_bytes_list = get_all_page_bytes(pdf_path)
                batches = create_batches(slide_bytes_list, DEFAULT_BATCH_SIZE)
                print(f"Created {len(batches)} batches for processing")

                # Step 5: Process batches (parallel for large presentations)
                all_results = {}
                total_tokens = {"input_tokens": 0, "output_tokens": 0}

                if len(batches) == 1:
                    # Single batch - process directly
                    _, result = self._process_batch(
                        batch=batches[0],
                        total_slides=total_slides,
                        pptx_name=pptx_path.name,
                        prompt_config=prompt_config,
                        tool_def=tool_def,
                        rate_limiter=rate_limiter,
                        source_id=source_id,
                        project_id=project_id
                    )
                    if result.get("success"):
                        all_results.update(result["slide_results"])
                        total_tokens["input_tokens"] += result["token_usage"].get("input_tokens", 0)
                        total_tokens["output_tokens"] += result["token_usage"].get("output_tokens", 0)
                    else:
                        return {"success": False, "error": result.get("error", "Unknown error")}
                else:
                    # Multiple batches - process in parallel
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {
                            executor.submit(
                                self._process_batch,
                                batch=batch,
                                total_slides=total_slides,
                                pptx_name=pptx_path.name,
                                prompt_config=prompt_config,
                                tool_def=tool_def,
                                rate_limiter=rate_limiter,
                                source_id=source_id,
                                project_id=project_id
                            ): batch[0][0]
                            for batch in batches
                        }

                        for future in as_completed(futures):
                            batch_start = futures[future]
                            try:
                                _, result = future.result()
                                if result.get("success"):
                                    all_results.update(result["slide_results"])
                                    total_tokens["input_tokens"] += result["token_usage"].get("input_tokens", 0)
                                    total_tokens["output_tokens"] += result["token_usage"].get("output_tokens", 0)
                                else:
                                    return {"success": False, "error": result.get("error")}
                            except CancelledException:
                                return {"success": False, "status": "cancelled", "error": "Processing cancelled"}
                            except Exception as e:
                                return {"success": False, "error": f"Batch {batch_start} failed: {str(e)}"}

                # Step 6: Build slide pages and use centralized output format
                pages = self._build_slide_pages(all_results)

                # Calculate character and token counts
                full_text = "\n".join(pages)
                character_count = len(full_text)
                token_count = count_tokens(full_text)

                # Build metadata for PPTX type
                model = prompt_config.get("model")
                metadata = {
                    "model_used": model,
                    "slides_processed": len(all_results),
                    "character_count": character_count,
                    "token_count": token_count
                }

                # Use centralized build_processed_output for consistent format
                output_content = build_processed_output(
                    pages=pages,
                    source_type="PPTX",
                    source_name=pptx_path.name,
                    metadata=metadata
                )

                print(f"PPTX extraction complete: {len(all_results)} slides processed")

                # Return processed content for processor to upload to Supabase Storage
                return {
                    "success": True,
                    "processed_content": output_content,
                    "total_slides": total_slides,
                    "slides_processed": len(all_results),
                    "character_count": character_count,
                    "token_count": token_count,
                    "token_usage": total_tokens,
                    "model_used": model,
                    "extracted_at": datetime.now().isoformat()
                }

            except Exception as e:
                print(f"Error processing PPTX: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

    def _process_batch(
        self,
        batch: List[Tuple[int, bytes]],
        total_slides: int,
        pptx_name: str,
        prompt_config: Dict[str, Any],
        tool_def: Dict[str, Any],
        rate_limiter: RateLimiter,
        source_id: str,
        project_id: str,
        max_retries: int = 3
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Process a batch of slides with Claude vision.

        Args:
            batch: List of (slide_number, slide_bytes) tuples
            total_slides: Total slides in presentation
            pptx_name: Original PPTX filename
            prompt_config: Prompt configuration
            tool_def: Tool definition
            rate_limiter: RateLimiter instance for API rate limiting
            source_id: Source UUID for cancellation check
            project_id: Project ID for cost tracking
            max_retries: Maximum retry attempts

        Returns:
            Tuple of (first_slide_in_batch, results_dict)
        """
        # Check for cancellation
        if task_service.is_cancelled(source_id):
            raise CancelledException("Processing cancelled by user")

        batch_start_slide = batch[0][0]
        batch_slide_numbers = [s[0] for s in batch]

        model = prompt_config.get("model", "claude-haiku-4-5-20251001")
        system_prompt = prompt_config.get("system_prompt", "")
        user_message_template = prompt_config.get("user_message", "")
        max_tokens = prompt_config.get("max_tokens", 16000)
        temperature = prompt_config.get("temperature", 0)

        # Build content blocks: one document block per slide
        content_blocks = []
        for slide_num, slide_bytes in batch:
            slide_base64 = encode_bytes_to_base64(slide_bytes)
            content_blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": slide_base64
                },
                "title": f"{pptx_name} - Slide {slide_num}",
            })

        # Build user message
        if len(batch) == 1:
            extraction_desc = f"slide {batch[0][0]}"
        else:
            extraction_desc = f"slides {batch[0][0]} to {batch[-1][0]}"

        slide_list = ", ".join(str(s) for s in batch_slide_numbers)

        user_message = user_message_template.format(
            total_pages=total_slides,
            extraction_description=extraction_desc,
            expected_tool_calls=len(batch),
            page_numbers=slide_list
        )

        content_blocks.append({
            "type": "text",
            "text": user_message
        })

        messages = [{"role": "user", "content": content_blocks}]

        # Retry loop with rate limiting
        last_error = None
        for attempt in range(max_retries):
            try:
                # Apply rate limiting before each API call
                rate_limiter.wait_if_needed()

                response = claude_service.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=[tool_def],
                    tool_choice={"type": "tool", "name": "submit_slide_extraction"},
                    project_id=project_id
                )

                slide_results = self._parse_tool_calls(response, batch_slide_numbers)

                return (batch_start_slide, {
                    "success": True,
                    "slide_results": slide_results,
                    "token_usage": response["usage"],
                    "model": response["model"]
                })

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "rate" in error_str or "429" in error_str or "overloaded" in error_str:
                    wait_time = (attempt + 1) * 30
                    print(f"Batch starting slide {batch_start_slide}: Rate limit hit, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    print(f"Batch starting slide {batch_start_slide}: Error - {e}")
                    if attempt < max_retries - 1:
                        time.sleep(5)

        return (batch_start_slide, {
            "success": False,
            "error": str(last_error)
        })

    def _parse_tool_calls(
        self,
        response: Dict[str, Any],
        expected_slide_numbers: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Parse slide extraction tool calls from Claude's response.

        Educational Note: Uses claude_parsing_utils.extract_tool_inputs() for
        generic tool parsing, then processes the PPTX-specific fields (slide_number,
        slide_title, text_content, visual_elements, layout_notes).

        Args:
            response: Claude API response
            expected_slide_numbers: List of slide numbers we expect

        Returns:
            Dict mapping slide_number to extraction results
        """
        results = {}

        # Use claude_parsing_utils for generic tool parsing
        tool_inputs = claude_parsing_utils.extract_tool_inputs(response, "submit_slide_extraction")

        # Process PPTX-specific fields from each tool call
        for input_data in tool_inputs:
            slide_num = input_data.get("slide_number")

            if slide_num in expected_slide_numbers:
                results[slide_num] = {
                    "slide_title": input_data.get("slide_title", "[NO TITLE]"),
                    "text_content": input_data.get("text_content", "[NO TEXT CONTENT]"),
                    "visual_elements": input_data.get("visual_elements", "[NO VISUAL ELEMENTS]"),
                    "layout_notes": input_data.get("layout_notes", "")
                }

        return results

    def _build_slide_pages(
        self,
        all_results: Dict[int, Dict[str, Any]]
    ) -> List[str]:
        """
        Build a list of slide content strings (one per slide).

        Educational Note: This returns just the page content for each slide.
        The page markers and header are added by build_processed_output.

        Args:
            all_results: Dict mapping slide numbers to extraction results

        Returns:
            List of formatted slide content strings
        """
        pages = []

        for slide_num in sorted(all_results.keys()):
            result = all_results[slide_num]
            slide_lines = []

            # Slide title
            title = result.get("slide_title", "[NO TITLE]")
            if title and title != "[NO TITLE]":
                slide_lines.append(f"# {title}")
                slide_lines.append("")

            # Text content
            text_content = result.get("text_content", "")
            if text_content and text_content != "[NO TEXT CONTENT]":
                slide_lines.append("## Content")
                slide_lines.append(text_content)
                slide_lines.append("")

            # Visual elements
            visual_elements = result.get("visual_elements", "")
            if visual_elements and visual_elements != "[NO VISUAL ELEMENTS]":
                slide_lines.append("## Visual Elements")
                slide_lines.append(visual_elements)
                slide_lines.append("")

            # Layout notes (optional, only if meaningful)
            layout_notes = result.get("layout_notes", "")
            if layout_notes and len(layout_notes) > 10:
                slide_lines.append("## Layout")
                slide_lines.append(layout_notes)
                slide_lines.append("")

            pages.append("\n".join(slide_lines))

        return pages


# Singleton instance
pptx_service = PPTXService()
