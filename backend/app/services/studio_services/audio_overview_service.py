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
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.integrations.elevenlabs import tts_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.services.tool_executors.studio_audio_executor import studio_audio_executor
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_studio_scripts_dir, get_studio_audio_dir


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
        direction: str = "Create an engaging audio overview of this content."
    ) -> Dict[str, Any]:
        """
        Generate an audio overview for a source.

        Educational Note: This is the main orchestrator that:
        1. Gets source metadata
        2. Runs the agentic script generation loop
        3. Converts script to audio
        4. Updates job status throughout

        Args:
            project_id: The project UUID
            source_id: The source UUID to generate overview for
            job_id: The job ID for status tracking
            direction: User's direction for the overview style/focus

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

        print(f"[AudioOverview] Starting job {job_id}")

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

        print(f"  Source: {source_name} ({token_count} tokens, large={is_large})")

        # Step 2: Setup paths
        scripts_dir = get_studio_scripts_dir(project_id)
        audio_dir = get_studio_audio_dir(project_id)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        script_path = scripts_dir / f"script_{source_id[:8]}_{timestamp}.txt"
        audio_filename = f"audio_{source_id[:8]}_{timestamp}.mp3"
        audio_path = audio_dir / audio_filename

        # Update progress
        studio_index_service.update_audio_job(
            project_id, job_id,
            progress="Generating script..."
        )

        # Step 3: Generate script via agentic loop
        script_result = self._generate_script(
            project_id=project_id,
            source_id=source_id,
            source_name=source_name,
            token_count=token_count,
            is_large=is_large,
            direction=direction,
            script_path=script_path,
            job_id=job_id
        )

        if not script_result.get("success"):
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error=script_result.get("error", "Script generation failed"),
                completed_at=datetime.now().isoformat()
            )
            return script_result

        print(f"  Script generated: {script_path.name}")

        # Update progress
        studio_index_service.update_audio_job(
            project_id, job_id,
            progress="Converting to audio...",
            script_path=str(script_path)
        )

        # Step 4: Convert script to audio
        script_text = script_path.read_text(encoding='utf-8')
        audio_result = tts_service.generate_audio(
            text=script_text,
            output_path=audio_path
        )

        if not audio_result.get("success"):
            studio_index_service.update_audio_job(
                project_id, job_id,
                status="error",
                error=f"TTS conversion failed: {audio_result.get('error')}",
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": f"TTS conversion failed: {audio_result.get('error')}",
                "script_path": str(script_path)
            }

        print(f"  Audio generated: {audio_path.name}")

        # Step 5: Update job as complete
        duration = (datetime.now() - started_at).total_seconds()
        audio_url = f"/api/v1/projects/{project_id}/studio/audio/{audio_filename}"

        studio_index_service.update_audio_job(
            project_id, job_id,
            status="ready",
            progress="Complete",
            audio_path=str(audio_path),
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
            "audio_path": str(audio_path),
            "audio_filename": audio_filename,
            "audio_url": audio_url,
            "script_path": str(script_path),
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
        script_path: Path,
        job_id: str
    ) -> Dict[str, Any]:
        """
        Generate script using agentic loop.

        Educational Note: The agent reads source content and writes script sections
        until it signals completion with is_final=True.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            source_name: Name of the source
            token_count: Token count of the source
            is_large: Whether source is large (needs chunked reading)
            direction: User's direction for the script
            script_path: Path to write the script file
            job_id: Job ID for progress updates

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

            print(f"    Iteration {iteration}/{max_iterations}")

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

                    print(f"      Tool: {tool_name}")

                    # Execute the tool
                    result, completed = studio_audio_executor.execute(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        project_id=project_id,
                        script_path=script_path
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
                        print(f"      Last batch detected at iteration {iteration}")

                    # Track if we've seen full content (small source)
                    if "FULL SOURCE CONTENT" in result:
                        full_content_seen = True
                        print(f"      Full content (small source) at iteration {iteration}")

            # Add tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Check if script generation is complete
            if is_complete:
                print(f"    Script complete in {iteration} iterations")
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
                if iterations_since_last_batch >= 2 and script_path.exists():
                    reason = "last batch" if last_batch_seen else "full content"
                    print(f"    Forcing completion after {iteration} iterations ({reason} seen)")
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
                print(f"    Unexpected end_turn at iteration {iteration}")
                # Try to use whatever script was written
                if script_path.exists():
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
        print(f"    Max iterations reached ({max_iterations})")
        if script_path.exists():
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
