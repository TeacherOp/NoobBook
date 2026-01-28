"""
Business Report Tool Executor - Handles tool execution for business report agent.

Executes: plan_business_report, analyze_csv_data, search_source_content, write_business_report
"""

import os
from typing import Dict, Any, List, Tuple
from datetime import datetime

from app.utils.path_utils import get_studio_dir
from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service
from app.services.ai_agents.csv_analyzer_agent import csv_analyzer_agent


class BusinessReportToolExecutor:
    """Executes business report agent tools."""

    TERMINATION_TOOL = "write_business_report"

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a business report tool.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters
            context: Execution context (project_id, job_id, collected_charts, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_business_report":
            result = self._execute_plan_report(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "analyze_csv_data":
            result = self._execute_analyze_csv(
                project_id, job_id, tool_input,
                context["collected_charts"], context["collected_analyses"]
            )
            return {"success": True, "message": result}, False

        elif tool_name == "search_source_content":
            result = self._execute_search_content(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "write_business_report":
            result = self._execute_write_report(
                project_id, job_id, tool_input, context
            )
            return result, True

        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def _execute_plan_report(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Execute plan_business_report tool."""
        title = tool_input.get("title", "Business Report")
        print(f"      Planning: {title[:50]}...")

        studio_index_service.update_business_report_job(
            project_id, job_id,
            title=title,
            sections=tool_input.get("sections", []),
            status_message="Report planned, analyzing data..."
        )

        num_sections = len(tool_input.get("sections", []))

        return f"Report plan saved. Title: '{title}', Sections: {num_sections}. Proceed to analyze data and write the report."

    def _execute_analyze_csv(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        collected_charts: List[Dict[str, str]],
        collected_analyses: List[Dict[str, Any]]
    ) -> str:
        """
        Execute analyze_csv_data tool.

        Calls csv_analyzer_agent internally for data analysis and chart generation.
        """
        csv_source_id = tool_input.get("csv_source_id", "")
        analysis_query = tool_input.get("analysis_query", "")
        section_context = tool_input.get("section_context", "")

        print(f"      Analyzing CSV {csv_source_id[:8]}... for: {section_context or 'general'}")

        studio_index_service.update_business_report_job(
            project_id, job_id,
            status_message=f"Analyzing data for {section_context or 'report'}..."
        )

        try:
            # Call csv_analyzer_agent directly
            result = csv_analyzer_agent.run(
                project_id=project_id,
                source_id=csv_source_id,
                query=analysis_query
            )

            if not result.get("success"):
                error_msg = result.get("error", "Analysis failed")
                return f"Error analyzing data: {error_msg}"

            # Extract results
            summary = result.get("summary", "No summary available")
            chart_paths = result.get("image_paths", [])

            # Track analysis
            analysis_info = {
                "query": analysis_query,
                "summary": summary,
                "chart_paths": chart_paths,
                "section_context": section_context
            }
            collected_analyses.append(analysis_info)

            # Track charts with metadata
            for chart_path in chart_paths:
                chart_info = {
                    "filename": chart_path,
                    "title": f"Chart for {section_context}" if section_context else "Data Chart",
                    "section": section_context,
                    "url": f"/api/v1/projects/{project_id}/ai-images/{chart_path}"
                }
                collected_charts.append(chart_info)

            # Update job with analyses
            studio_index_service.update_business_report_job(
                project_id, job_id,
                analyses=collected_analyses,
                charts=collected_charts
            )

            # Build response for Claude
            response_parts = [f"Analysis complete for: {section_context or 'data analysis'}"]
            response_parts.append(f"\nSummary: {summary}")

            if chart_paths:
                response_parts.append(f"\nGenerated {len(chart_paths)} chart(s):")
                for chart_path in chart_paths:
                    response_parts.append(f"  - {chart_path}")
                response_parts.append("\nUse these exact filenames in your markdown: ![Description](filename.png)")

            print(f"      Charts generated: {len(chart_paths)}")

            return "\n".join(response_parts)

        except Exception as e:
            error_msg = f"Error during CSV analysis: {str(e)}"
            print(f"      {error_msg}")
            return error_msg

    def _execute_search_content(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """
        Execute search_source_content tool.

        Searches non-CSV sources for context.
        """
        source_id = tool_input.get("source_id", "")
        search_query = tool_input.get("search_query", "")
        section_context = tool_input.get("section_context", "")

        print(f"      Searching source {source_id[:8]}... for: {search_query[:30]}")

        try:
            # Get content from Supabase Storage
            content = storage_service.download_processed_file(project_id, source_id)

            if not content:
                return f"Source content not found for {source_id}"

            # Return a sample of the content
            max_length = 3000
            if len(content) > max_length:
                content = content[:max_length] + "\n\n[Content truncated for context...]"

            return f"Content from source (for {section_context or 'context'}):\n\n{content}"

        except Exception as e:
            error_msg = f"Error searching source content: {str(e)}"
            print(f"      {error_msg}")
            return error_msg

    def _execute_write_report(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute write_business_report tool (termination)."""
        markdown_content = tool_input.get("markdown_content", "")
        charts_included = tool_input.get("charts_included", [])

        collected_charts = context["collected_charts"]
        collected_analyses = context["collected_analyses"]
        iterations = context["iterations"]
        input_tokens = context["input_tokens"]
        output_tokens = context["output_tokens"]
        report_type = context["report_type"]

        # Estimate word count from content
        word_count = len(markdown_content.split()) if markdown_content else 0

        print(f"      Writing markdown ({len(markdown_content)} chars, ~{word_count} words)")

        try:
            # Replace chart filenames with full URLs
            final_markdown = markdown_content
            for chart_info in collected_charts:
                filename = chart_info["filename"]
                url = chart_info["url"]
                final_markdown = final_markdown.replace(f"({filename})", f"({url})")

            # Save markdown file
            studio_dir = get_studio_dir(project_id)
            reports_dir = os.path.join(studio_dir, "business_reports")
            os.makedirs(reports_dir, exist_ok=True)

            markdown_filename = f"{job_id}.md"
            markdown_path = os.path.join(reports_dir, markdown_filename)

            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(final_markdown)

            print(f"      Saved: {markdown_filename}")

            # Get job info for title
            job = studio_index_service.get_business_report_job(project_id, job_id)
            title = job.get("title", "Business Report")

            # Update job to ready
            studio_index_service.update_business_report_job(
                project_id, job_id,
                status="ready",
                status_message="Business report generated successfully!",
                markdown_file=markdown_filename,
                markdown_url=f"/api/v1/projects/{project_id}/studio/business-reports/{markdown_filename}",
                preview_url=f"/api/v1/projects/{project_id}/studio/business-reports/{job_id}/preview",
                word_count=word_count,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "title": title,
                "markdown_file": markdown_filename,
                "markdown_url": f"/api/v1/projects/{project_id}/studio/business-reports/{markdown_filename}",
                "preview_url": f"/api/v1/projects/{project_id}/studio/business-reports/{job_id}/preview",
                "charts": collected_charts,
                "analyses_count": len(collected_analyses),
                "word_count": word_count,
                "report_type": report_type,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error saving business report: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_business_report_job(
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
business_report_tool_executor = BusinessReportToolExecutor()
