"""
Quiz Service - Generates quiz questions from source content.

Educational Note: This service uses Claude to generate multiple choice quiz
questions for testing knowledge. Like flash cards, this is a single-call service:

1. Read source content (chunked or full)
2. Call Claude with generate_quiz tool
3. Parse and return the quiz questions

The tool-based approach ensures structured output with questions, options,
correct answers, hints, and explanations.
"""
from typing import Dict, Any
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.services.integrations.supabase import storage_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils, source_content_utils


class QuizService:
    """
    Service for generating quiz questions from source content.

    Educational Note: Quiz questions are generated in a single Claude call
    using the generate_quiz tool for structured output.
    """

    def __init__(self):
        """Initialize service with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tool = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("quiz")
        return self._prompt_config

    def _load_tool(self) -> Dict[str, Any]:
        """Load the quiz tool definition."""
        if self._tool is None:
            self._tool = tool_loader.load_tool("studio_tools", "quiz_tool")
        return self._tool



    def generate_quiz(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create quiz questions covering the key concepts."
    ) -> Dict[str, Any]:
        """
        Generate quiz questions for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: User's direction for what to focus on

        Returns:
            Dict with success status, questions array, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_quiz_job(
            project_id, job_id,
            status="processing",
            progress="Reading source content...",
            started_at=datetime.now().isoformat()
        )

        print(f"[Quiz] Starting job {job_id}")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")

            # Get source content
            studio_index_service.update_quiz_job(
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

            # Call Claude with the quiz tool
            studio_index_service.update_quiz_job(
                project_id, job_id,
                progress="Generating quiz questions..."
            )

            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=[tool],
                tool_choice={"type": "tool", "name": "generate_quiz"},
                project_id=project_id
            )

            # Extract tool use result
            # Note: extract_tool_inputs returns a LIST of inputs (one per tool call)
            tool_inputs_list = claude_parsing_utils.extract_tool_inputs(
                response, "generate_quiz"
            )

            if not tool_inputs_list or "questions" not in tool_inputs_list[0]:
                raise ValueError("Failed to generate quiz - no questions returned")

            tool_inputs = tool_inputs_list[0]  # Get first (and only) tool call
            questions = tool_inputs["questions"]
            topic_summary = tool_inputs.get("topic_summary", "")

            # Calculate generation time
            generation_time = (datetime.now() - started_at).total_seconds()

            # Update job with results
            studio_index_service.update_quiz_job(
                project_id, job_id,
                status="ready",
                progress="Complete",
                questions=questions,
                topic_summary=topic_summary,
                question_count=len(questions),
                generation_time_seconds=round(generation_time, 1),
                completed_at=datetime.now().isoformat()
            )

            print(f"[Quiz] Generated {len(questions)} questions in {generation_time:.1f}s")

            return {
                "success": True,
                "questions": questions,
                "topic_summary": topic_summary,
                "question_count": len(questions),
                "source_name": source_name,
                "generation_time": generation_time
            }

        except Exception as e:
            print(f"[Quiz] Error: {e}")
            studio_index_service.update_quiz_job(
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
quiz_service = QuizService()
