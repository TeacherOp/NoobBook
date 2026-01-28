"""
Studio Audio Executor - Executes tools for audio script generation.

Educational Note: This executor handles two tools for the audio overview agent:
1. read_source_content: Reads source content (full for small, chunk by chunk for large)
2. write_script_section: Writes/appends script sections to file

The agent reads content incrementally and writes script sections as it goes,
ensuring the script covers all source material even for large sources.
"""
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from app.services.source_services import source_index_service
from app.services.integrations.supabase import storage_service
from app.utils.path_utils import get_studio_scripts_dir


class StudioAudioExecutor:
    """
    Executor for studio audio generation tools.

    Educational Note: This executor supports an agentic loop where Claude:
    1. Reads source content (read_source_content) - 5 chunks at a time
    2. Writes script sections (write_script_section)
    3. Repeats until all content is covered
    """

    # Token threshold for "small" sources - read full content
    SMALL_SOURCE_THRESHOLD = 2000
    # Number of chunks to return per read for large sources
    CHUNKS_PER_BATCH = 5

    def __init__(self):
        """Initialize the executor."""
        pass

    def execute(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        project_id: str,
        script_path: Optional[Path] = None
    ) -> Tuple[str, bool]:
        """
        Execute a studio audio tool.

        Args:
            tool_name: The tool to execute
            tool_input: The tool input parameters
            project_id: The project UUID
            script_path: Path for script file (required for write_script_section)

        Returns:
            Tuple of (result_string, is_complete)
            is_complete is True when script generation is finished
        """
        if tool_name == "read_source_content":
            return self._execute_read_source(tool_input, project_id)
        elif tool_name == "write_script_section":
            return self._execute_write_script(tool_input, project_id, script_path)
        else:
            return f"Unknown tool: {tool_name}", False

    # =========================================================================
    # Read Source Content
    # =========================================================================

    def _execute_read_source(
        self,
        tool_input: Dict[str, Any],
        project_id: str
    ) -> Tuple[str, bool]:
        """
        Execute read_source_content tool.

        For small sources (<2000 tokens): Returns full processed content
        For large sources: Returns 5 chunks at a time (batch reading)

        Args:
            tool_input: Contains source_id and optional start_chunk (1-indexed)
            project_id: The project UUID

        Returns:
            Tuple of (content_string, False) - is_complete always False for reads
        """
        source_id = tool_input.get("source_id")
        start_chunk = tool_input.get("start_chunk", 1)  # 1-indexed, default to first chunk

        if not source_id:
            return "Error: source_id is required", False

        # Get source metadata
        source = source_index_service.get_source_from_index(project_id, source_id)
        if not source:
            return f"Error: Source not found: {source_id}", False

        # Get token count from embedding_info
        embedding_info = source.get("embedding_info", {})
        token_count = embedding_info.get("token_count", 0)
        is_embedded = embedding_info.get("is_embedded", False)

        # Small source or not embedded - return full processed content
        if token_count < self.SMALL_SOURCE_THRESHOLD or not is_embedded:
            return self._read_full_processed(project_id, source_id, source.get("name", ""))

        # Large source - return batch of 5 chunks
        return self._read_chunk_batch(project_id, source_id, source.get("name", ""), start_chunk)

    def _read_full_processed(
        self,
        project_id: str,
        source_id: str,
        source_name: str
    ) -> Tuple[str, bool]:
        """Read full processed content for small sources from Supabase Storage."""
        content = storage_service.download_processed_file(project_id, source_id)

        if not content:
            return f"Error: Processed file not found for source {source_id}", False

        result = (
            f"=== FULL SOURCE CONTENT ===\n"
            f"Source: {source_name}\n"
            f"Type: small source (under {self.SMALL_SOURCE_THRESHOLD} tokens)\n"
            f"---\n\n"
            f"{content}"
        )
        return result, False

    def _read_chunk_batch(
        self,
        project_id: str,
        source_id: str,
        source_name: str,
        start_chunk: int
    ) -> Tuple[str, bool]:
        """
        Read a batch of 5 chunks starting from start_chunk from Supabase Storage.

        Educational Note: For large sources, we read 5 chunks at a time.
        Claude writes a script section, then reads the next batch, appends,
        and repeats until all chunks are covered.
        """
        chunks = storage_service.list_source_chunks(project_id, source_id)

        if not chunks:
            return f"Error: No chunks found for source {source_id}", False

        total_chunks = len(chunks)

        # Validate start_chunk (1-indexed)
        if start_chunk < 1 or start_chunk > total_chunks:
            return (
                f"Error: Invalid start_chunk {start_chunk}. "
                f"Source has {total_chunks} chunks (1 to {total_chunks})."
            ), False

        # Calculate batch range (0-indexed internally)
        start_idx = start_chunk - 1
        end_idx = min(start_idx + self.CHUNKS_PER_BATCH, total_chunks)
        batch_chunks = chunks[start_idx:end_idx]

        # Build the batch content
        result_parts = [
            f"=== CHUNKS {start_chunk} to {end_idx} of {total_chunks} ===",
            f"Source: {source_name}",
            f"---"
        ]

        for i, chunk in enumerate(batch_chunks):
            chunk_num = start_idx + i + 1  # 1-indexed
            text = chunk.get('text', '')
            result_parts.append(f"\n[Chunk {chunk_num}]")
            result_parts.append(text)

        result_parts.append(f"\n---")

        # Add navigation hints
        if end_idx < total_chunks:
            next_start = end_idx + 1
            remaining = total_chunks - end_idx
            result_parts.append(
                f"Next batch: start_chunk={next_start} ({remaining} chunks remaining). "
                f"Write a script section for this content, then read the next batch."
            )
        else:
            result_parts.append(
                "This is the last batch. Write your final script section with is_final=true."
            )

        return "\n".join(result_parts), False

    # =========================================================================
    # Write Script Section
    # =========================================================================

    def _execute_write_script(
        self,
        tool_input: Dict[str, Any],
        project_id: str,
        script_path: Optional[Path]
    ) -> Tuple[str, bool]:
        """
        Execute write_script_section tool.

        Args:
            tool_input: Contains section_number, operation, script_content, is_final
            project_id: The project UUID
            script_path: Path to write the script file

        Returns:
            Tuple of (result_string, is_complete)
            is_complete is True when is_final=True
        """
        section_number = tool_input.get("section_number", 1)
        operation = tool_input.get("operation", "write")
        script_content = tool_input.get("script_content", "")
        is_final = tool_input.get("is_final", False)

        if not script_content:
            return "Error: script_content is required", False

        if not script_path:
            # Use default path if not provided
            scripts_dir = get_studio_scripts_dir(project_id)
            script_path = scripts_dir / f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        try:
            # Ensure directory exists
            script_path.parent.mkdir(parents=True, exist_ok=True)

            # Write or append
            if operation == "write":
                script_path.write_text(script_content, encoding='utf-8')
                result = f"Section {section_number} written to script."
            else:  # append
                with open(script_path, 'a', encoding='utf-8') as f:
                    # Add separator between sections
                    f.write("\n\n")
                    f.write(script_content)
                result = f"Section {section_number} appended to script."

            if is_final:
                word_count = len(script_content.split())
                result += f" Script finalized with ~{word_count} words in this section."
                return result, True
            else:
                result += " Continue with next section."
                return result, False

        except Exception as e:
            return f"Error writing script: {str(e)}", False


# Singleton instance
studio_audio_executor = StudioAudioExecutor()
