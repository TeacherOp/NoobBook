"""
Wireframe Agent Service - AI agent for generating UI/UX wireframes.

Orchestrates the wireframe generation workflow using an agentic loop:
1. Agent plans wireframe sections (plan_wireframe tool)
2. Agent generates elements for each section incrementally (add_wireframe_section tool)
3. Agent finalizes the complete wireframe (finalize_wireframe - termination)

This agentic approach allows for larger wireframes by distributing output
across multiple iterations, avoiding token limit issues.
"""

import uuid
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.source_content_utils import get_source_content
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service
from app.services.source_services import source_index_service
from app.services.tool_executors.wireframe_tool_executor import wireframe_tool_executor


class WireframeAgentService:
    """Wireframe generation agent - orchestration with agentic loop."""

    AGENT_NAME = "wireframe_agent"
    MAX_ITERATIONS = 15  # Allow enough iterations for complex wireframes

    def __init__(self):
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("wireframe_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    def generate_wireframe(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create a wireframe for the main page layout.",
    ) -> Dict[str, Any]:
        """
        Run the agent to generate a wireframe using an agentic loop.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: User's direction for what to wireframe

        Returns:
            Dict with success status, elements, and metadata
        """
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now()

        # Update job status
        studio_index_service.update_wireframe_job(
            project_id,
            job_id,
            status="processing",
            progress="Starting wireframe generation...",
            started_at=started_at.isoformat(),
        )

        print(f"[WireframeAgent] Starting (job_id: {job_id[:8]})")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")

            # Get source content
            studio_index_service.update_wireframe_job(
                project_id, job_id, progress="Analyzing content..."
            )

            source_content = get_source_content(project_id, source_id, max_chars=15000)
            if not source_content or source_content.startswith("Error"):
                raise ValueError("No content found for source")

            # Build user message from config
            user_message = config.get("user_message", "").format(
                source_content=source_content, direction=direction
            )

            messages = [{"role": "user", "content": user_message}]

            total_input_tokens = 0
            total_output_tokens = 0

            # Initialize accumulator for wireframe elements
            accumulated_elements = []
            wireframe_metadata = {
                "title": "Wireframe",
                "description": "",
                "canvas_width": 1200,
                "canvas_height": 800,
                "sections": [],
            }

            for iteration in range(1, self.MAX_ITERATIONS + 1):
                print(f"  Iteration {iteration}/{self.MAX_ITERATIONS}")

                # Update progress
                studio_index_service.update_wireframe_job(
                    project_id,
                    job_id,
                    progress=f"Generating wireframe (iteration {iteration})...",
                )

                response = claude_service.send_message(
                    messages=messages,
                    system_prompt=config["system_prompt"],
                    model=config["model"],
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"],
                    tools=tools["all_tools"] if isinstance(tools, dict) else tools,
                    tool_choice={"type": "any"},
                    project_id=project_id,
                )

                total_input_tokens += response["usage"]["input_tokens"]
                total_output_tokens += response["usage"]["output_tokens"]

                content_blocks = response.get("content_blocks", [])
                serialized_content = claude_parsing_utils.serialize_content_blocks(
                    content_blocks
                )
                messages.append({"role": "assistant", "content": serialized_content})

                # Process tool calls
                tool_results = []

                for block in content_blocks:
                    block_type = (
                        getattr(block, "type", None)
                        if hasattr(block, "type")
                        else block.get("type")
                    )

                    if block_type == "tool_use":
                        tool_name = (
                            getattr(block, "name", "")
                            if hasattr(block, "name")
                            else block.get("name", "")
                        )
                        tool_input = (
                            getattr(block, "input", {})
                            if hasattr(block, "input")
                            else block.get("input", {})
                        )
                        tool_id = (
                            getattr(block, "id", "")
                            if hasattr(block, "id")
                            else block.get("id", "")
                        )

                        print(f"    Tool: {tool_name}")

                        # Build execution context with accumulated state
                        context = {
                            "project_id": project_id,
                            "job_id": job_id,
                            "source_id": source_id,
                            "source_name": source_name,
                            "iterations": iteration,
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens,
                            "accumulated_elements": accumulated_elements,
                            "wireframe_metadata": wireframe_metadata,
                        }

                        # Execute tool via executor
                        result, is_termination = wireframe_tool_executor.execute_tool(
                            tool_name, tool_input, context
                        )

                        # Update accumulated state from result
                        if "accumulated_elements" in result:
                            accumulated_elements = result["accumulated_elements"]
                        if "wireframe_metadata" in result:
                            wireframe_metadata = result["wireframe_metadata"]

                        if is_termination:
                            print(f"  Completed in {iteration} iterations")
                            generation_time = (
                                datetime.now() - started_at
                            ).total_seconds()

                            # Update job with final results
                            studio_index_service.update_wireframe_job(
                                project_id,
                                job_id,
                                status="ready",
                                progress="Complete",
                                title=wireframe_metadata.get("title", "Wireframe"),
                                description=wireframe_metadata.get("description", ""),
                                elements=accumulated_elements,
                                canvas_width=wireframe_metadata.get(
                                    "canvas_width", 1200
                                ),
                                canvas_height=wireframe_metadata.get(
                                    "canvas_height", 800
                                ),
                                element_count=len(accumulated_elements),
                                generation_time_seconds=round(generation_time, 1),
                                completed_at=datetime.now().isoformat(),
                            )

                            final_result = {
                                "success": True,
                                "title": wireframe_metadata.get("title", "Wireframe"),
                                "description": wireframe_metadata.get(
                                    "description", ""
                                ),
                                "elements": accumulated_elements,
                                "element_count": len(accumulated_elements),
                                "source_name": source_name,
                                "generation_time": generation_time,
                                "iterations": iteration,
                                "usage": {
                                    "input_tokens": total_input_tokens,
                                    "output_tokens": total_output_tokens,
                                },
                            }

                            self._save_execution(
                                project_id,
                                execution_id,
                                job_id,
                                messages,
                                final_result,
                                started_at.isoformat(),
                                source_id,
                            )

                            return final_result

                        # Add tool result for next iteration
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": result.get("message", str(result)),
                            }
                        )

                if tool_results:
                    messages.append({"role": "user", "content": tool_results})

            # Max iterations reached
            print(f"  Max iterations reached ({self.MAX_ITERATIONS})")
            generation_time = (datetime.now() - started_at).total_seconds()

            # If we have accumulated elements, consider it a partial success
            if accumulated_elements:
                studio_index_service.update_wireframe_job(
                    project_id,
                    job_id,
                    status="ready",
                    progress="Complete (partial)",
                    title=wireframe_metadata.get("title", "Wireframe"),
                    description=wireframe_metadata.get("description", ""),
                    elements=accumulated_elements,
                    canvas_width=wireframe_metadata.get("canvas_width", 1200),
                    canvas_height=wireframe_metadata.get("canvas_height", 800),
                    element_count=len(accumulated_elements),
                    generation_time_seconds=round(generation_time, 1),
                    completed_at=datetime.now().isoformat(),
                )

                partial_result = {
                    "success": True,
                    "title": wireframe_metadata.get("title", "Wireframe"),
                    "description": wireframe_metadata.get("description", ""),
                    "elements": accumulated_elements,
                    "element_count": len(accumulated_elements),
                    "source_name": source_name,
                    "generation_time": generation_time,
                    "iterations": self.MAX_ITERATIONS,
                    "partial": True,
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                    },
                }

                self._save_execution(
                    project_id,
                    execution_id,
                    job_id,
                    messages,
                    partial_result,
                    started_at.isoformat(),
                    source_id,
                )

                return partial_result

            # No elements at all - error
            error_result = {
                "success": False,
                "error": f"Agent reached maximum iterations ({self.MAX_ITERATIONS}) without generating elements",
                "iterations": self.MAX_ITERATIONS,
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                },
            }

            studio_index_service.update_wireframe_job(
                project_id,
                job_id,
                status="error",
                error=error_result["error"],
                completed_at=datetime.now().isoformat(),
            )

            self._save_execution(
                project_id,
                execution_id,
                job_id,
                messages,
                error_result,
                started_at.isoformat(),
                source_id,
            )

            return error_result

        except Exception as e:
            print(f"[WireframeAgent] Error: {e}")
            studio_index_service.update_wireframe_job(
                project_id,
                job_id,
                status="error",
                error=str(e),
                completed_at=datetime.now().isoformat(),
            )
            return {"success": False, "error": str(e)}

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        job_id: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: str,
    ) -> None:
        """Save execution log for debugging."""
        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Generate wireframe (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id},
        )


# Singleton instance
wireframe_agent_service = WireframeAgentService()
