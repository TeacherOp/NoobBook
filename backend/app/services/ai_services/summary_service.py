"""
Summary Service - Generate concise summaries for processed sources.

Educational Note: This service generates summaries for source documents
after processing is complete. It uses a smart sampling strategy to handle
documents of varying sizes while keeping API costs low.

Summary Strategy:
- Small sources (not chunked, <2500 tokens): Send entire content
- Large sources (chunked): Send evenly distributed sample of chunks
- Input budget: ~20k tokens max (8 chunks at ~2500 tokens each)
- Output: 150-200 tokens summary

The summary is stored in the source index under the 'summary' field.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.integrations.supabase import storage_service
from app.config import prompt_loader
from app.utils import claude_parsing_utils


class SummaryService:
    """
    Service for generating source summaries.

    Educational Note: Uses Haiku model for cost-effective summarization.
    Input: $1/M tokens, Output: $3/M tokens
    ~20k input + 200 output = ~$0.02 per summary

    Prompt config is loaded from data/prompts/summary_prompt.json
    via prompt_loader for consistency with other AI tools.
    """

    # Maximum chunks to send for summarization (budget: ~20k tokens)
    MAX_CHUNKS = 8

    def __init__(self):
        """Initialize the summary service with cached prompt config."""
        self._prompt_config: Optional[Dict[str, Any]] = None

    def _get_prompt_config(self) -> Dict[str, Any]:
        """
        Load and cache the prompt config.

        Educational Note: We cache the config to avoid reading
        the file on every summary generation request. Uses prompt_loader
        for consistent prompt loading across all AI tools.
        """
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("summary")
            if self._prompt_config is None:
                raise ValueError("summary_prompt.json not found in data/prompts/")
        return self._prompt_config

    def _get_chunk_indices(self, total_chunks: int, chunks_to_select: int) -> List[int]:
        """
        Get evenly distributed chunk indices, always including first and last.

        Educational Note: Uses linear interpolation to distribute selection.
        Formula: index[i] = round(i * (total - 1) / (select - 1))

        This ensures:
        - First chunk (intro/context) is always included
        - Last chunk (conclusion) is always included
        - Middle chunks are evenly spaced

        Args:
            total_chunks: Total number of chunks available
            chunks_to_select: Number of chunks to select

        Returns:
            List of chunk indices (0-based)
        """
        if chunks_to_select >= total_chunks:
            return list(range(total_chunks))

        if chunks_to_select == 1:
            return [0]

        if chunks_to_select == 2:
            return [0, total_chunks - 1]

        # Calculate step size for even distribution
        step = (total_chunks - 1) / (chunks_to_select - 1)

        # Generate indices
        indices = [round(i * step) for i in range(chunks_to_select)]

        return indices

    def _load_processed_content(self, project_id: str, source_id: str) -> Optional[str]:
        """
        Load the full processed content for a source from Supabase Storage.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Processed text content or None if not found
        """
        return storage_service.download_processed_file(project_id, source_id)

    def _load_selected_chunks(
        self,
        project_id: str,
        source_id: str
    ) -> Optional[str]:
        """
        Load evenly distributed chunks and concatenate them from Supabase Storage.

        Educational Note: For large documents, we select a sample of chunks
        to stay within our token budget while maintaining coverage of the
        document's content from beginning to end.

        Args:
            project_id: The project UUID
            source_id: The source UUID

        Returns:
            Concatenated chunk content with separators, or None if failed
        """
        # Load all chunks for this source from Supabase Storage
        all_chunks = storage_service.list_source_chunks(project_id, source_id)

        if not all_chunks:
            return None

        # Determine how many chunks to select
        chunks_to_select = min(self.MAX_CHUNKS, len(all_chunks))

        # Get evenly distributed indices
        indices = self._get_chunk_indices(len(all_chunks), chunks_to_select)

        # Build content from selected chunks
        content_parts = []
        for idx in indices:
            if idx < len(all_chunks):
                chunk = all_chunks[idx]
                page_num = chunk.get('page_number', idx + 1)
                content_parts.append(f"[Page {page_num}]\n{chunk['text']}")

        return "\n\n---\n\n".join(content_parts)

    def _build_user_message(
        self,
        config: Dict[str, Any],
        content: str,
        source_metadata: Dict[str, Any],
        is_sampled: bool,
        total_pages: int,
        pages_sent: int
    ) -> str:
        """
        Build the user message using the template from prompt config.

        Educational Note: The user_message template is stored in the prompt config
        file (summary_prompt.json) for consistency across AI tools. This keeps
        all prompt-related content in one place for easy tuning.

        Args:
            config: The prompt config containing user_message template
            content: The content to summarize
            source_metadata: Source metadata from index
            is_sampled: Whether content is a sample (not full document)
            total_pages: Total pages/chunks in the document
            pages_sent: Number of pages/chunks being sent

        Returns:
            Formatted user message from template
        """
        category = source_metadata.get('category', 'document')
        name = source_metadata.get('name', 'Unknown')
        file_ext = source_metadata.get('file_extension', '')

        # Build content info line based on whether content is sampled
        if is_sampled:
            content_info = (
                f"Content Provided: {pages_sent} pages sampled at equal intervals "
                f"(pages include beginning, end, and evenly distributed middle sections)"
            )
        else:
            content_info = f"Content Provided: Full document ({pages_sent} pages)"

        # Get template from config and fill in placeholders
        template = config.get('user_message', '')

        return template.format(
            document_type=category.upper(),
            file_extension=file_ext,
            document_name=name,
            total_pages=total_pages,
            content_info=content_info,
            content=content
        )

    def generate_summary(
        self,
        project_id: str,
        source_id: str,
        source_metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a summary for a processed source.

        Educational Note: This is the main entry point for summary generation.
        It determines the best strategy based on whether the source is chunked,
        loads the appropriate content, and calls the AI for summarization.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            source_metadata: Source metadata from the index

        Returns:
            Dict with summary and metadata, or None if failed:
            {
                "summary": "The summary text...",
                "model": "claude-haiku-4-5-20250514",
                "usage": {"input_tokens": X, "output_tokens": Y},
                "generated_at": "2025-11-29T...",
                "strategy": "full" | "sampled",
                "pages_used": N
            }
        """
        # Load prompt configuration
        config = self._get_prompt_config()

        # Check if source is embedded (has chunks)
        embedding_info = source_metadata.get('embedding_info', {})
        is_embedded = embedding_info.get('is_embedded', False)
        chunk_count = embedding_info.get('chunk_count', 0)

        # Get total pages from processing_info
        processing_info = source_metadata.get('processing_info', {})
        total_pages = processing_info.get('total_pages', 1)

        # Determine content loading strategy
        if is_embedded and chunk_count > 0:
            # Source has chunks - use sampling strategy
            content = self._load_selected_chunks(project_id, source_id)
            is_sampled = chunk_count > self.MAX_CHUNKS
            pages_sent = min(self.MAX_CHUNKS, chunk_count)
        else:
            # Source is not chunked - send full processed content
            content = self._load_processed_content(project_id, source_id)
            is_sampled = False
            pages_sent = total_pages

        if not content:
            print(f"No content found for source {source_id}")
            return None

        # Build user message using template from config
        user_message = self._build_user_message(
            config=config,
            content=content,
            source_metadata=source_metadata,
            is_sampled=is_sampled,
            total_pages=total_pages,
            pages_sent=pages_sent
        )

        # Call Claude API
        try:
            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config.get('system_prompt', ''),
                model=config.get('model'),
                max_tokens=config.get('max_tokens'),
                temperature=config.get('temperature'),
                project_id=project_id
            )

            # Use claude_parsing_utils to extract text from content_blocks
            summary_text = claude_parsing_utils.extract_text(response).strip()

            if not summary_text:
                print(f"Empty summary returned for source {source_id}")
                return None

            return {
                "summary": summary_text,
                "model": response.get('model'),
                "usage": response.get('usage'),
                "generated_at": datetime.now().isoformat(),
                "strategy": "sampled" if is_sampled else "full",
                "pages_used": pages_sent,
                "total_pages": total_pages
            }

        except Exception as e:
            print(f"Error generating summary for source {source_id}: {e}")
            return None


# Singleton instance for easy import
summary_service = SummaryService()
