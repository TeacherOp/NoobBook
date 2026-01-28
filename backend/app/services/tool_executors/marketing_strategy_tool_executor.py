"""
Marketing Strategy Tool Executor - Handles tool execution for marketing strategy agent.

Tool handlers extracted from marketing_strategy_agent_service.py for separation of concerns.
Agent handles orchestration, executor handles tool-specific logic.
"""

from typing import Dict, Any, Tuple
from datetime import datetime

from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service


class MarketingStrategyToolExecutor:
    """Executes marketing strategy agent tools."""

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a tool and return result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters from Claude
            context: Execution context (project_id, job_id, sections_written, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_marketing_strategy":
            result = self._handle_plan(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "write_marketing_section":
            sections_written = context.get("sections_written", 0)
            result_msg, is_complete, file_path = self._handle_write_section(
                project_id, job_id, tool_input, sections_written
            )

            if is_complete:
                # Finalize and return termination result
                final_result = self._finalize(
                    project_id=project_id,
                    job_id=job_id,
                    source_id=context.get("source_id"),
                    file_path=file_path,
                    sections_written=sections_written + 1,
                    iterations=context.get("iterations", 0),
                    input_tokens=context.get("input_tokens", 0),
                    output_tokens=context.get("output_tokens", 0)
                )
                return final_result, True

            return {"success": True, "message": result_msg, "file_path": file_path}, False

        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}, False

    def _handle_plan(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle plan_marketing_strategy tool call."""
        document_title = tool_input.get("document_title", "Marketing Strategy Document")
        product_name = tool_input.get("product_name", "Unknown Product")
        sections = tool_input.get("sections", [])

        print(f"      Planning: {document_title} ({len(sections)} sections)")

        # Update job with plan
        studio_index_service.update_marketing_strategy_job(
            project_id, job_id,
            document_title=document_title,
            product_name=product_name,
            target_market=tool_input.get("target_market"),
            planned_sections=sections,
            planning_notes=tool_input.get("planning_notes"),
            total_sections=len(sections),
            status_message=f"Planned {len(sections)} sections, starting to write..."
        )

        return (
            f"Marketing strategy plan saved successfully. "
            f"Document: '{document_title}', Product: '{product_name}', "
            f"Sections planned: {len(sections)}. "
            f"Now proceed to write each section using the write_marketing_section tool."
        )

    def _handle_write_section(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        current_sections_written: int
    ) -> Tuple[str, bool, str]:
        """
        Handle write_marketing_section tool call.

        We use our own counter (current_sections_written + 1) instead of trusting
        the LLM's section_number to prevent duplicate sections.

        Returns:
            Tuple of (result_message, is_complete, file_path)
        """
        actual_section_number = current_sections_written + 1
        agent_section_number = tool_input.get("section_number", actual_section_number)

        operation = tool_input.get("operation", "append")
        is_last_section = tool_input.get("is_last_section", False)
        section_title = tool_input.get("section_title", "")
        markdown_content = tool_input.get("markdown_content", "")

        # Log mismatch for debugging
        if agent_section_number != actual_section_number:
            print(f"      Note: Agent sent section {agent_section_number}, using actual count {actual_section_number}")

        print(f"      Writing section {actual_section_number}: {section_title} (is_last: {is_last_section})")

        try:
            markdown_filename = f"{job_id}.md"

            # Get job info for document title and total sections
            job = studio_index_service.get_marketing_strategy_job(project_id, job_id)
            document_title = job.get("document_title", "Marketing Strategy Document") if job else "Marketing Strategy Document"
            total_sections = job.get("total_sections", 0) if job else 0

            # Write or append content to Supabase Storage
            if operation == "write":
                # First section - create file with title
                content = f"# {document_title}\n\n"
                content += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
                content += "---\n\n"
                content += markdown_content
                content += "\n\n"
                storage_service.upload_studio_file(
                    project_id, "marketing_strategies", job_id, markdown_filename, content
                )
            else:
                # Subsequent sections - append
                content = markdown_content + "\n\n"
                storage_service.append_studio_file(
                    project_id, "marketing_strategies", job_id, markdown_filename, content
                )

            studio_index_service.update_marketing_strategy_job(
                project_id, job_id,
                sections_written=actual_section_number,
                current_section=section_title,
                markdown_file=markdown_filename,
                status_message=f"Writing section {actual_section_number}/{total_sections}: {section_title}..."
            )

            # Build result message
            result_msg = f"Section {actual_section_number} '{section_title}' written successfully."
            if is_last_section:
                result_msg += " Marketing strategy document is now complete."
            elif total_sections > 0:
                remaining = total_sections - actual_section_number
                result_msg += f" Progress: {actual_section_number}/{total_sections} sections complete. {remaining} section(s) remaining."

            return result_msg, is_last_section, markdown_filename

        except Exception as e:
            error_msg = f"Error writing section {actual_section_number}: {str(e)}"
            print(f"      {error_msg}")
            return error_msg, False, None

    def _finalize(
        self,
        project_id: str,
        job_id: str,
        source_id: str,
        file_path: str,
        sections_written: int,
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Finalize the marketing strategy document and update job status."""
        try:
            # Get job info
            job = studio_index_service.get_marketing_strategy_job(project_id, job_id)
            document_title = job.get("document_title", "Marketing Strategy") if job else "Marketing Strategy"
            markdown_filename = f"{job_id}.md"

            # Update job to ready
            studio_index_service.update_marketing_strategy_job(
                project_id, job_id,
                status="ready",
                status_message="Marketing strategy generated successfully!",
                markdown_file=markdown_filename,
                markdown_filename=markdown_filename,
                preview_url=f"/api/v1/projects/{project_id}/studio/marketing-strategies/{job_id}/preview",
                download_url=f"/api/v1/projects/{project_id}/studio/marketing-strategies/{job_id}/download",
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "document_title": document_title,
                "markdown_file": markdown_filename,
                "preview_url": f"/api/v1/projects/{project_id}/studio/marketing-strategies/{job_id}/preview",
                "download_url": f"/api/v1/projects/{project_id}/studio/marketing-strategies/{job_id}/download",
                "sections_written": sections_written,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error finalizing marketing strategy: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_marketing_strategy_job(
                project_id, job_id,
                status="error",
                error_message=error_msg
            )

            return {
                "success": False,
                "error_message": error_msg,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }


# Singleton instance
marketing_strategy_tool_executor = MarketingStrategyToolExecutor()
