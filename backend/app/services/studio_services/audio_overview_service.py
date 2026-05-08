"""
Audio Overview Service - Generates audio overviews from source content.

Educational Note: This service implements an agentic loop pattern:
1. Claude reads source content (read_source_content tool)
2. Claude writes script sections (write_script_section tool)
3. Loop continues until is_final=True
4. Script is converted to audio via ElevenLabs TTS

For large sources, Claude reads chunks incrementally and writes script sections
as it goes. For small sources, it reads all content at once.

Tools:
- read_source_content: Reads source content (full or chunk by chunk)
- write_script_section: Writes/appends script sections, signals completion
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.integrations.claude import claude_service

logger = logging.getLogger(__name__)
from app.services.integrations.elevenlabs import tts_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.services.tool_executors.studio_audio_executor import studio_audio_executor
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.services.integrations.supabase import storage_service


class AudioOverviewService:
    """
    Service for generating audio overviews from source content.

    Educational Note: This service orchestrates the full pipeline:
    1. Agentic script generation (Claude reads content, writes script)
    2. TTS conversion (ElevenLabs converts script to audio)
    """

    AGENT_NAME = "audio_overview"
    MAX_ITERATIONS = 25  # Reasonable limit - most scripts finish in 5-15 iterations

    def __init__(self):
        """Initialize service with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("audio_script")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        """Load tools for the audio agent."""
        if self._tools is None:
            self._tools = tool_loader.load_tools_from_category("studio_tools")
        return self._tools

    # =========================================================================
    # Main Entry Point (for background task)
    # =========================================================================

    def generate_audio_overview(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create an engaging audio overview of this content.",
        previous_content: str = None,
        edit_instructions: str = None
    ) -> Dict[str, Any]:
        """
        Generate an audio overview for a source, or edit a previous audio script.

        Educational Note: This is the main orchestrator that:
        1. Gets source metadata
        2. Runs the agentic script generation loop
        3. Converts script to audio
        4. Updates job status throughout

        For edits, the previous script is passed to the agent as context so
        Claude can refine it based on the user's edit instructions.

        Args:
            project_id: The project UUID
            source_id: The source UUID to generate overview for
            job_id: The job ID for status tracking
            direction: User's direction for the overview style/focus
            previous_content: Previous script text to refine (for edits)
            edit_instructions: Instructions for how to edit the previous audio

        Returns:
            Dict with success status, audio file path, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_audio_job(
            project_id, job_id,
            status="processing",
            progress="Loading source...",
            started_at=datetime.now().isoformat()
        )

        # Step 1: Get source metadata
        source = source_index_service.get_source_from_index(project_id, source_id)
        if not source:
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error=f"Source not found: {source_id}",
                completed_at=datetime.now().isoformat()
            )
            return {"success": False, "error": f"Source not found: {source_id}"}

        source_name = source.get("name", "Unknown")
        embedding_info = source.get("embedding_info", {})
        token_count = embedding_info.get("token_count", 0)
        is_large = token_count >= studio_audio_executor.SMALL_SOURCE_THRESHOLD

        # Step 2: Setup filenames for Supabase Storage
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        script_filename = "script.txt"
        audio_filename = f"audio_{source_id[:8]}_{timestamp}.mp3"

        # Update progress
        studio_index_service.update_audio_job(
            project_id, job_id,
            progress="Generating script..."
        )

        # Step 3: Generate script via agentic loop (writes to Supabase Storage)
        script_result = self._generate_script(
            project_id=project_id,
            source_id=source_id,
            source_name=source_name,
            token_count=token_count,
            is_large=is_large,
            direction=direction,
            job_id=job_id,
            previous_content=previous_content,
            edit_instructions=edit_instructions
        )

        if not script_result.get("success"):
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error=script_result.get("error", "Script generation failed"),
                completed_at=datetime.now().isoformat()
            )
            return script_result

        # Update progress
        studio_index_service.update_audio_job(
            project_id, job_id,
            progress="Converting to audio..."
        )

        # Step 4: Read script from Supabase and convert to audio bytes
        script_text = storage_service.download_studio_file(
            project_id, "audio", job_id, script_filename
        )
        if not script_text:
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error="Script file not found in storage after generation",
                completed_at=datetime.now().isoformat()
            )
            return {"success": False, "error": "Script file not found in storage"}

        audio_result = tts_service.generate_audio_bytes(text=script_text)

        if not audio_result.get("success"):
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error=f"TTS conversion failed: {audio_result.get('error')}",
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": f"TTS conversion failed: {audio_result.get('error')}"
            }

        # Upload audio bytes to Supabase Storage
        audio_bytes = audio_result["audio_bytes"]
        storage_path = storage_service.upload_studio_binary(
            project_id, "audio", job_id, audio_filename, audio_bytes, "audio/mpeg"
        )
        if not storage_path:
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error="Failed to upload audio to storage",
                completed_at=datetime.now().isoformat()
            )
            return {"success": False, "error": "Failed to upload audio to storage"}

        # Step 5: Update job as complete
        duration = (datetime.now() - started_at).total_seconds()
        audio_url = f"/api/v1/projects/{project_id}/studio/audio/{job_id}/{audio_filename}"

        studio_index_service.update_audio_job(
            project_id, job_id,
            status="ready",
            progress="Complete",
            audio_filename=audio_filename,
            audio_url=audio_url,
            audio_info={
                "file_size_bytes": audio_result.get("file_size_bytes"),
                "estimated_duration_seconds": audio_result.get("estimated_duration_seconds"),
                "word_count": len(script_text.split()),
                "voice_id": audio_result.get("voice_id"),
                "model_id": audio_result.get("model_id")
            },
            completed_at=datetime.now().isoformat()
        )

        return {
            "success": True,
            "job_id": job_id,
            "audio_filename": audio_filename,
            "audio_url": audio_url,
            "source_id": source_id,
            "source_name": source_name,
            "direction": direction,
            "duration_seconds": duration,
            "script_iterations": script_result.get("iterations", 0),
            "script_word_count": len(script_text.split()),
            "audio_info": audio_result,
            "usage": script_result.get("usage", {})
        }

    # =========================================================================
    # Script Generation (Agentic Loop)
    # =========================================================================

    def _generate_script(
        self,
        project_id: str,
        source_id: str,
        source_name: str,
        token_count: int,
        is_large: bool,
        direction: str,
        job_id: str,
        previous_content: str = None,
        edit_instructions: str = None
    ) -> Dict[str, Any]:
        """
        Generate script using agentic loop.

        Educational Note: The agent reads source content and writes script sections
        until it signals completion with is_final=True. Script is stored in
        Supabase Storage at: {project_id}/audio/{job_id}/script.txt

        For edits, the previous script is appended to the user message so Claude
        can refine it. Source reading is skipped when previous content is available.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            source_name: Name of the source
            token_count: Token count of the source
            is_large: Whether source is large (needs chunked reading)
            direction: User's direction for the script
            job_id: Job ID for progress updates and Supabase storage path
            previous_content: Previous script text to refine (for edits)
            edit_instructions: Instructions for how to edit the previous script

        Returns:
            Dict with success status, iterations, and usage stats
        """
        config = self._load_config()
        tools = self._load_tools()

        # Build user message from config template
        user_message = config["user_message"].format(
            direction=direction,
            source_id=source_id,
            source_name=source_name,
            token_count=token_count,
            is_large=str(is_large)
        )

        # Append edit context if editing a previous audio script
        if previous_content and edit_instructions:
            edit_context = (
                f"\n\n=== PREVIOUS SCRIPT (refine based on edit instructions) ===\n"
                f"{previous_content}\n"
                f"=== END PREVIOUS SCRIPT ===\n\n"
                f"EDIT INSTRUCTIONS: {edit_instructions}\n\n"
                f"Use the previous script as baseline. Apply the edits. "
                f"Keep unchanged sections. Write the complete revised script "
                f"using write_script_section. You do NOT need to read the source "
                f"again — the previous script already covers it."
            )
            user_message += edit_context

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0
        last_batch_seen = False  # Track if we've seen "last batch" message
        iterations_since_last_batch = 0  # Track iterations after last batch
        full_content_seen = False  # Track if we've seen full content (small source)

        # Smaller limit for small sources (should finish in 2-3 iterations)
        max_iterations = 5 if not is_large else self.MAX_ITERATIONS

        for iteration in range(1, max_iterations + 1):
            # Update progress
            studio_index_service.update_audio_job(
                project_id, job_id,
                progress=f"Generating script (step {iteration})..."
            )

            # Call Claude API
            response = claude_service.send_message(
                messages=messages,
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=tools,
                tool_choice={"type": "any"},
                project_id=project_id
            )

            # Track usage
            total_input_tokens += response["usage"]["input_tokens"]
            total_output_tokens += response["usage"]["output_tokens"]

            # Add assistant response to messages
            content_blocks = response.get("content_blocks", [])
            serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
            messages.append({"role": "assistant", "content": serialized_content})

            # Process tool calls
            tool_results = []
            is_complete = False

            for block in content_blocks:
                block_type = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")

                if block_type == "tool_use":
                    tool_name = getattr(block, "name", "") if hasattr(block, "name") else block.get("name", "")
                    tool_input = getattr(block, "input", {}) if hasattr(block, "input") else block.get("input", {})
                    tool_id = getattr(block, "id", "") if hasattr(block, "id") else block.get("id", "")

                    # Execute the tool
                    result, completed = studio_audio_executor.execute(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        project_id=project_id,
                        job_id=job_id
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result
                    })

                    if completed:
                        is_complete = True

                    # Track if this is the last batch of content
                    if "This is the last batch" in result:
                        last_batch_seen = True

                    # Track if we've seen full content (small source)
                    if "FULL SOURCE CONTENT" in result:
                        full_content_seen = True

            # Add tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Check if script generation is complete
            if is_complete:
                return {
                    "success": True,
                    "iterations": iteration,
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens
                    }
                }

            # Force completion if we've seen all content and Claude isn't finishing
            if last_batch_seen or full_content_seen:
                iterations_since_last_batch += 1
                # Give Claude 2 extra iterations to finish properly
                if iterations_since_last_batch >= 2 and storage_service.download_studio_file(project_id, "audio", job_id, "script.txt"):
                    reason = "last batch" if last_batch_seen else "full content"
                    return {
                        "success": True,
                        "iterations": iteration,
                        "usage": {
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens
                        },
                        "note": f"Script generation forced after {reason}"
                    }

            # Check for end_turn without tool use (shouldn't happen, but handle it)
            if claude_parsing_utils.is_end_turn(response) and not tool_results:
                logger.warning("Unexpected end_turn at iteration %s", iteration)
                # Try to use whatever script was written
                if storage_service.download_studio_file(project_id, "audio", job_id, "script.txt"):
                    return {
                        "success": True,
                        "iterations": iteration,
                        "usage": {
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens
                        },
                        "note": "Script generation ended early"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Script generation ended without producing output",
                        "iterations": iteration
                    }

        # Max iterations reached
        logger.warning("Audio script generation hit max iterations (%s)", max_iterations)
        if storage_service.download_studio_file(project_id, "audio", job_id, "script.txt"):
            return {
                "success": True,
                "iterations": max_iterations,
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens
                },
                "note": f"Script generation used all {max_iterations} iterations"
            }
        else:
            return {
                "success": False,
                "error": f"Max iterations reached ({max_iterations}) without completing script",
                "iterations": max_iterations
            }


# Singleton instance
audio_overview_service = AudioOverviewService()
