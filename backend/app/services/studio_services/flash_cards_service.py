"""
Flash Cards Service - Generates flash cards from source content.

Educational Note: This service uses Claude to generate flash cards for
learning and memorization. Unlike the audio overview service which uses
an agentic loop, this is a single-call service:

1. Read source content (chunked or full)
2. Call Claude with generate_flash_cards tool
3. Parse and return the flash cards

The tool-based approach ensures structured output (front/back/category).
"""
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.config import prompt_loader, tool_loader
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils, source_content_utils
# from app.utils.path_utils import get_chunks_dir, get_processed_dir  <-- Removed unused imports


class FlashCardsService:
    """
    Service for generating flash cards from source content.

    Educational Note: Flash cards are generated in a single Claude call
    using the generate_flash_cards tool for structured output.
    """

    def __init__(self):
        """Initialize service with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tool = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("flash_cards")
        return self._prompt_config

    def _load_tool(self) -> Dict[str, Any]:
        """Load the flash cards tool definition."""
        if self._tool is None:
            self._tool = tool_loader.load_tool("studio_tools", "flash_cards_tool")
        return self._tool



    def generate_flash_cards(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create flash cards covering the key concepts."
    ) -> Dict[str, Any]:
        """
        Generate flash cards for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: User's direction for what to focus on

        Returns:
            Dict with success status, cards array, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_flash_card_job(
            project_id, job_id,
            status="processing",
            progress="Reading source content...",
            started_at=datetime.now().isoformat()
        )

        print(f"[FlashCards] Starting job {job_id}")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")

            # Get source content
            studio_index_service.update_flash_card_job(
                project_id, job_id,
                progress="Analyzing content..."
            )

            content = source_content_utils.get_sampled_source_content(
                project_id, source_id, max_tokens=8000
            )
            if not content:
                raise ValueError("No content found for source")

            # Load config and tool
            config = self._load_config()
            tool = self._load_tool()

            # Build the user message
            user_message = config["user_message_template"].format(
                direction=direction,
                content=content[:15000]  # Limit content to ~15k chars
            )

            # Call Claude with the flash cards tool
            studio_index_service.update_flash_card_job(
                project_id, job_id,
                progress="Generating flash cards..."
            )

            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=[tool],
                tool_choice={"type": "tool", "name": "generate_flash_cards"},
                project_id=project_id
            )

            # Extract tool use result
            # Note: extract_tool_inputs returns a LIST of inputs (one per tool call)
            tool_inputs_list = claude_parsing_utils.extract_tool_inputs(
                response, "generate_flash_cards"
            )

            if not tool_inputs_list or "cards" not in tool_inputs_list[0]:
                raise ValueError("Failed to generate flash cards - no cards returned")

            tool_inputs = tool_inputs_list[0]  # Get first (and only) tool call
            cards = tool_inputs["cards"]
            topic_summary = tool_inputs.get("topic_summary", "")

            # Calculate generation time
            generation_time = (datetime.now() - started_at).total_seconds()

            # Update job with results
            studio_index_service.update_flash_card_job(
                project_id, job_id,
                status="ready",
                progress="Complete",
                cards=cards,
                topic_summary=topic_summary,
                card_count=len(cards),
                generation_time_seconds=round(generation_time, 1),
                completed_at=datetime.now().isoformat()
            )

            print(f"[FlashCards] Generated {len(cards)} cards in {generation_time:.1f}s")

            return {
                "success": True,
                "cards": cards,
                "topic_summary": topic_summary,
                "card_count": len(cards),
                "source_name": source_name,
                "generation_time": generation_time
            }

        except Exception as e:
            print(f"[FlashCards] Error: {e}")
            studio_index_service.update_flash_card_job(
                project_id, job_id,
                status="error",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
flash_cards_service = FlashCardsService()
