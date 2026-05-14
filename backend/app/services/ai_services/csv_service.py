"""
CSV Service - AI service for analyzing CSV files and generating summaries.

Educational Note: This service uses a simple agentic loop pattern:
1. Claude receives the filename and available tools
2. Claude calls csv_analyzer to understand the data
3. Claude calls return_csv_summary with the final summary (termination)

The CSV content is NOT sent to Claude directly (could be huge).
Instead, when Claude calls csv_analyzer, we execute it locally and
return the results to Claude for analysis.

CSV files are NOT chunked or embedded - they are analyzed on-demand.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.services.tool_executors.csv_tool_executor import csv_tool_executor
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class CSVService:
    """
    AI service for CSV analysis and summary generation.

    Educational Note: Uses Haiku model with csv_analyzer tool.
    Claude analyzes the tool output and generates a concise summary.
    """

    # 40 matches the project-wide ceiling. CSV summarisation almost
    # always finishes in 2-3 rounds on Haiku, but the ceiling is
    # consistent with every other agent now.
    MAX_ITERATIONS = 40
    TERMINATION_TOOL = "return_csv_summary"

    def __init__(self):
        """Initialize with lazy-loaded config and tools."""
        self._prompt_config: Optional[Dict[str, Any]] = None
        self._tools: Optional[list] = None

    def _get_prompt_config(self) -> Dict[str, Any]:
        """Load and cache prompt config."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("csv_processor")
            if self._prompt_config is None:
                raise ValueError("csv_processor.json not found in data/prompts/")
        return self._prompt_config

    def _get_tools(self) -> list:
        """Load and cache tools from csv_tool category."""
        if self._tools is None:
            tools_config = tool_loader.load_tools_for_agent("csv_tool")
            self._tools = tools_config["all_tools"]
        return self._tools

    def analyze_csv(
        self,
        project_id: str,
        source_id: str,
        csv_file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a CSV file and generate a summary.

        Educational Note: Simple agentic loop:
        1. Send initial message with source_id
        2. When Claude calls csv_analyzer, executor reads file and analyzes
        3. When Claude calls return_csv_summary, extract and return summary

        Args:
            project_id: Project ID (for file path and cost tracking)
            source_id: Source ID (filename is {source_id}.csv in raw folder)
            csv_file_path: Optional explicit path to the CSV file (e.g. temp directory
                           during processing). Passed through to csv_tool_executor.

        Returns:
            Dict with summary, row_count, column_count, and metadata
        """
        config = self._get_prompt_config()
        tools = self._get_tools()

        # Build initial user message from template
        user_message = config.get("user_message", "Analyze this CSV file.").format(
            filename=f"{source_id}.csv"
        )

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0

        logger.info("Analyzing CSV source %s", source_id[:8])

        for iteration in range(1, self.MAX_ITERATIONS + 1):

            # Call Claude API
            response = claude_service.send_message(
                messages=messages,
                system_prompt=config.get("system_prompt", ""),
                model=config.get("model"),
                max_tokens=config.get("max_tokens"),
                temperature=config.get("temperature"),
                tools=tools,
                project_id=project_id
            )

            # Track token usage
            total_input_tokens += response["usage"]["input_tokens"]
            total_output_tokens += response["usage"]["output_tokens"]

            # Serialize and add assistant response
            content_blocks = response.get("content_blocks", [])
            serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
            messages.append({"role": "assistant", "content": serialized_content})

            # Extract tool use blocks using parsing utils
            tool_blocks = claude_parsing_utils.extract_tool_use_blocks(response)

            if not tool_blocks:
                # Claude ended the turn without calling return_csv_summary.
                # Previous behaviour was to `continue`, which just re-asked
                # Claude with the same conversation — guaranteed to waste
                # every remaining iteration on the same dead path
                # (12 hits of "End turn without summary tool - unexpected"
                # in prod). Treat the text Claude produced as the summary
                # and exit cleanly.
                if claude_parsing_utils.is_end_turn(response):
                    text = claude_parsing_utils.extract_text(response).strip()
                    if text:
                        logger.info(
                            "CSV analysis ended on text response (iter %d, no termination tool)",
                            iteration,
                        )
                        # Claude produced only prose — it never called the
                        # csv_analyzer tool, so we have no real row/column
                        # counts to report. Use None (not 0) so a frontend
                        # that displays row/column metadata can render
                        # "—" rather than silently showing "0 rows".
                        return self._build_result(
                            {"summary": text, "row_count": None, "column_count": None},
                            iteration,
                            total_input_tokens,
                            total_output_tokens,
                        )
                    logger.warning("End turn with no text and no tool — bailing")
                    break
                continue

            # Process each tool call
            tool_results_data = []

            for tool_block in tool_blocks:
                tool_name = tool_block["name"]
                tool_input = tool_block["input"]
                tool_id = tool_block["id"]

                # TERMINATION: return_csv_summary means we're done
                if tool_name == self.TERMINATION_TOOL:
                    logger.info("CSV analysis completed in %d iterations", iteration)
                    return self._build_result(
                        tool_input,
                        iteration,
                        total_input_tokens,
                        total_output_tokens
                    )

                # csv_analyzer: Execute and return results
                elif tool_name == "csv_analyzer":
                    result, _ = csv_tool_executor.execute_tool(
                        tool_input, project_id, source_id, csv_file_path=csv_file_path
                    )
                    # Format result as readable string for Claude
                    content = self._format_tool_result(result)
                    tool_results_data.append({
                        "tool_use_id": tool_id,
                        "result": content
                    })

            # Build and add tool results using parsing utils
            if tool_results_data:
                tool_results_content = claude_parsing_utils.build_tool_result_content(tool_results_data)
                messages.append({"role": "user", "content": tool_results_content})

        # Max iterations reached without summary
        logger.warning("Max iterations reached (%d)", self.MAX_ITERATIONS)
        return {
            "success": False,
            "error": f"Analysis did not complete within {self.MAX_ITERATIONS} iterations",
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
        }

    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        """
        Format tool result as readable string for Claude.

        Educational Note: Claude needs readable output to understand
        the data and generate a good summary. JSON is harder to parse.
        """
        if not result.get("success"):
            return f"Error: {result.get('error', 'Unknown error')}"

        operation = result.get("operation", "unknown")
        output_parts = [f"## CSV Analysis Result ({operation})"]

        if operation == "summary":
            output_parts.append(f"\nRows: {result.get('total_rows', 0)}")
            output_parts.append(f"Columns: {result.get('total_columns', 0)}")

            output_parts.append("\n### Column Information")
            column_info = result.get("column_info", {})
            for col, info in column_info.items():
                col_type = info.get("type", "unknown")
                non_empty = info.get("non_empty", 0)
                unique = info.get("unique", 0)
                output_parts.append(f"- {col} ({col_type}): {non_empty} values, {unique} unique")

            # Add sample data preview
            sample_data = result.get("sample_data", [])
            if sample_data:
                output_parts.append("\n### Sample Data (First 3 Rows)")
                for i, row in enumerate(sample_data[:3], 1):
                    row_str = ", ".join(f"{k}: {v}" for k, v in list(row.items())[:5])
                    output_parts.append(f"{i}. {row_str}")

            # Add recommendations
            recommendations = result.get("recommendations", [])
            if recommendations:
                output_parts.append("\n### Recommendations")
                for rec in recommendations:
                    output_parts.append(f"- {rec}")

        elif operation == "profile":
            output_parts.append(f"\nRows: {result.get('row_count', 0)}")
            output_parts.append(f"Columns: {result.get('column_count', 0)}")
            output_parts.append(f"Quality Score: {result.get('data_quality_score', 0)}%")

            output_parts.append("\n### Column Profiles")
            profiles = result.get("column_profiles", {})
            for col, profile in profiles.items():
                output_parts.append(f"\n**{col}** ({profile.get('type', 'unknown')})")
                output_parts.append(f"  Completeness: {profile.get('completeness', 'N/A')}")
                output_parts.append(f"  Unique: {profile.get('unique_values', 0)}")
                if "mean" in profile:
                    output_parts.append(f"  Mean: {profile.get('mean')}, Median: {profile.get('median')}")

        else:
            # Generic JSON output for other operations
            output_parts.append(f"\n{json.dumps(result, indent=2, default=str)}")

        return "\n".join(output_parts)

    def _build_result(
        self,
        tool_input: Dict[str, Any],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """
        Build the final result from return_csv_summary tool input.

        Educational Note: The termination tool's input IS the result.
        We just add metadata (iterations, token usage, timestamp).
        """
        return {
            "success": True,
            "summary": tool_input.get("summary", ""),
            "row_count": tool_input.get("row_count", 0),
            "column_count": tool_input.get("column_count", 0),
            "iterations": iterations,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "generated_at": datetime.now().isoformat()
        }


# Singleton instance
csv_service = CSVService()
