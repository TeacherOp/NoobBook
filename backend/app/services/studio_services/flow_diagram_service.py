"""
Flow Diagram Service - Generates Mermaid diagrams from source content.

Educational Note: This service uses Claude to generate Mermaid diagram syntax
for visual process and relationship mapping. Unlike mind maps which use a custom
node structure rendered with React Flow, flow diagrams use Mermaid.js which
handles its own rendering.

Mermaid supports many diagram types:
- Flowcharts (graph TD/LR)
- Sequence diagrams
- State diagrams
- ER diagrams
- Class diagrams
- Pie charts
- Gantt charts
- User journeys

The tool-based approach ensures structured output with valid Mermaid syntax.
"""
from typing import Dict, Any
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.services.integrations.supabase import storage_service


class FlowDiagramService:
    """
    Service for generating Mermaid flow diagrams from source content.

    Educational Note: Flow diagrams are generated in a single Claude call
    using the generate_flow_diagram tool for structured Mermaid syntax output.
    """

    def __init__(self):
        """Initialize service with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tool = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("flow_diagram")
        return self._prompt_config

    def _load_tool(self) -> Dict[str, Any]:
        """Load the flow diagram tool definition."""
        if self._tool is None:
            self._tool = tool_loader.load_tool("studio_tools", "flow_diagram_tool")
        return self._tool

    def _get_source_content(
        self,
        project_id: str,
        source_id: str,
        max_tokens: int = 8000
    ) -> str:
        """
        Get source content for flow diagram generation.

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

    def generate_flow_diagram(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create a diagram showing the key processes and relationships."
    ) -> Dict[str, Any]:
        """
        Generate a Mermaid flow diagram for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: User's direction for what to focus on

        Returns:
            Dict with success status, mermaid_syntax, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_flow_diagram_job(
            project_id, job_id,
            status="processing",
            progress="Reading source content...",
            started_at=datetime.now().isoformat()
        )

        print(f"[FlowDiagram] Starting job {job_id}")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")

            # Get source content
            studio_index_service.update_flow_diagram_job(
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

            # Call Claude with the flow diagram tool
            studio_index_service.update_flow_diagram_job(
                project_id, job_id,
                progress="Generating diagram..."
            )

            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=[tool],
                tool_choice={"type": "tool", "name": "generate_flow_diagram"},
                project_id=project_id
            )

            # Extract tool use result
            tool_inputs_list = claude_parsing_utils.extract_tool_inputs(
                response, "generate_flow_diagram"
            )

            if not tool_inputs_list or "mermaid_syntax" not in tool_inputs_list[0]:
                raise ValueError("Failed to generate flow diagram - no mermaid syntax returned")

            tool_inputs = tool_inputs_list[0]
            mermaid_syntax = tool_inputs["mermaid_syntax"]
            diagram_type = tool_inputs.get("diagram_type", "flowchart")
            title = tool_inputs.get("title", "Flow Diagram")
            description = tool_inputs.get("description", "")

            # Calculate generation time
            generation_time = (datetime.now() - started_at).total_seconds()

            # Update job with results
            studio_index_service.update_flow_diagram_job(
                project_id, job_id,
                status="ready",
                progress="Complete",
                mermaid_syntax=mermaid_syntax,
                diagram_type=diagram_type,
                title=title,
                description=description,
                generation_time_seconds=round(generation_time, 1),
                completed_at=datetime.now().isoformat()
            )

            print(f"[FlowDiagram] Generated {diagram_type} diagram in {generation_time:.1f}s")

            return {
                "success": True,
                "mermaid_syntax": mermaid_syntax,
                "diagram_type": diagram_type,
                "title": title,
                "description": description,
                "source_name": source_name,
                "generation_time": generation_time
            }

        except Exception as e:
            print(f"[FlowDiagram] Error: {e}")
            studio_index_service.update_flow_diagram_job(
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
flow_diagram_service = FlowDiagramService()
