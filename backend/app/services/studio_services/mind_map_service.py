"""
Mind Map Service - Generates hierarchical mind maps from source content.

Educational Note: This service uses Claude to generate structured mind maps
for visual concept mapping. Like the flash cards service, this is a single-call
service using tool-based extraction:

1. Read source content (chunked or full)
2. Call Claude with generate_mind_map tool
3. Parse and return the hierarchical node structure

The tool-based approach ensures structured output with proper parent-child
relationships (id, label, parent_id, node_type, description).
"""
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.integrations.supabase import storage_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils


class MindMapService:
    """
    Service for generating mind maps from source content.

    Educational Note: Mind maps are generated in a single Claude call
    using the generate_mind_map tool for structured hierarchical output.
    """

    def __init__(self):
        """Initialize service with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tool = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("mind_map")
        return self._prompt_config

    def _load_tool(self) -> Dict[str, Any]:
        """Load the mind map tool definition."""
        if self._tool is None:
            self._tool = tool_loader.load_tool("studio_tools", "mind_map_tool")
        return self._tool

    def _get_source_content(
        self,
        project_id: str,
        source_id: str,
        max_tokens: int = 8000
    ) -> str:
        """
        Get source content for mind map generation.

        Educational Note: For large sources, we sample chunks evenly
        to stay within token limits while covering the full content.
        Content is downloaded from Supabase Storage.
        """
        # Get source metadata
        source = source_index_service.get_source_from_index(project_id, source_id)
        if not source:
            return ""

        # Token count is stored in embedding_info
        embedding_info = source.get("embedding_info", {}) or {}
        token_count = embedding_info.get("token_count", 0) or 0

        # For small sources, read the processed file from Supabase Storage
        if token_count < max_tokens:
            processed_content = storage_service.download_processed_file(
                project_id, source_id
            )
            if processed_content:
                return processed_content

        # For large sources, get chunks from Supabase Storage
        chunks = storage_service.list_source_chunks(project_id, source_id)
        if not chunks:
            return ""

        # Sample evenly across chunks
        total_chunks = len(chunks)
        sample_count = min(20, total_chunks)  # Max 20 chunks
        step = max(1, total_chunks // sample_count)

        content_parts = []
        for i in range(0, total_chunks, step):
            if len(content_parts) >= sample_count:
                break
            chunk_text = chunks[i].get("text", "")
            content_parts.append(chunk_text.strip())

        return '\n\n---\n\n'.join(content_parts)

    def generate_mind_map(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create a mind map covering the key concepts and their relationships."
    ) -> Dict[str, Any]:
        """
        Generate a mind map for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: User's direction for what to focus on

        Returns:
            Dict with success status, nodes array, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_mind_map_job(
            project_id, job_id,
            status="processing",
            progress="Reading source content...",
            started_at=datetime.now().isoformat()
        )

        print(f"[MindMap] Starting job {job_id}")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")

            # Get source content
            studio_index_service.update_mind_map_job(
                project_id, job_id,
                progress="Analyzing content..."
            )

            content = self._get_source_content(project_id, source_id)
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

            # Call Claude with the mind map tool
            studio_index_service.update_mind_map_job(
                project_id, job_id,
                progress="Generating mind map..."
            )

            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=[tool],
                tool_choice={"type": "tool", "name": "generate_mind_map"},
                project_id=project_id
            )

            # Extract tool use result
            # Note: extract_tool_inputs returns a LIST of inputs (one per tool call)
            tool_inputs_list = claude_parsing_utils.extract_tool_inputs(
                response, "generate_mind_map"
            )

            if not tool_inputs_list or "nodes" not in tool_inputs_list[0]:
                raise ValueError("Failed to generate mind map - no nodes returned")

            tool_inputs = tool_inputs_list[0]  # Get first (and only) tool call
            nodes = tool_inputs["nodes"]
            topic_summary = tool_inputs.get("topic_summary", "")

            # Validate the mind map structure
            self._validate_mind_map(nodes)

            # Calculate generation time
            generation_time = (datetime.now() - started_at).total_seconds()

            # Update job with results
            studio_index_service.update_mind_map_job(
                project_id, job_id,
                status="ready",
                progress="Complete",
                nodes=nodes,
                topic_summary=topic_summary,
                node_count=len(nodes),
                generation_time_seconds=round(generation_time, 1),
                completed_at=datetime.now().isoformat()
            )

            print(f"[MindMap] Generated {len(nodes)} nodes in {generation_time:.1f}s")

            return {
                "success": True,
                "nodes": nodes,
                "topic_summary": topic_summary,
                "node_count": len(nodes),
                "source_name": source_name,
                "generation_time": generation_time
            }

        except Exception as e:
            print(f"[MindMap] Error: {e}")
            studio_index_service.update_mind_map_job(
                project_id, job_id,
                status="error",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": str(e)
            }

    def _validate_mind_map(self, nodes: List[Dict[str, Any]]) -> None:
        """
        Validate the mind map structure.

        Checks:
        1. Exactly one root node (parent_id is None/null)
        2. All parent_ids reference valid node ids
        3. No orphaned nodes (except root)
        """
        if not nodes:
            raise ValueError("Mind map has no nodes")

        # Find root nodes
        root_nodes = [n for n in nodes if n.get("parent_id") is None]
        if len(root_nodes) == 0:
            raise ValueError("Mind map has no root node")
        if len(root_nodes) > 1:
            # Just warn, don't fail - use first as root
            print(f"[MindMap] Warning: {len(root_nodes)} root nodes found, expected 1")

        # Build id set for validation
        node_ids = {n["id"] for n in nodes}

        # Check all parent_ids are valid
        for node in nodes:
            parent_id = node.get("parent_id")
            if parent_id is not None and parent_id not in node_ids:
                print(f"[MindMap] Warning: Node {node['id']} has invalid parent_id: {parent_id}")


# Singleton instance
mind_map_service = MindMapService()
