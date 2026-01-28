"""
Wireframe Tool Executor - Handles tool calls from the wireframe agent.

Executes:
- plan_wireframe: Initial wireframe structure planning
- add_wireframe_section: Add elements for a section
- finalize_wireframe: Complete the wireframe (termination)
"""

from typing import Dict, Any, Tuple
from app.utils.excalidraw_utils import convert_to_excalidraw_elements


class WireframeToolExecutor:
    """Executes wireframe agent tool calls."""

    def execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters
            context: Execution context with state

        Returns:
            Tuple of (result dict, is_termination_tool)
        """
        if tool_name == "plan_wireframe":
            return self._handle_plan_wireframe(tool_input, context)
        elif tool_name == "add_wireframe_section":
            return self._handle_add_section(tool_input, context)
        elif tool_name == "finalize_wireframe":
            return self._handle_finalize(tool_input, context)
        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}, False

    def _handle_plan_wireframe(
        self, tool_input: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Handle the plan_wireframe tool - sets up wireframe metadata and sections.
        """
        title = tool_input.get("title", "Wireframe")
        description = tool_input.get("description", "")
        sections = tool_input.get("sections", [])
        canvas_width = tool_input.get("canvas_width", 1200)
        canvas_height = tool_input.get("canvas_height", 800)

        # Update wireframe metadata
        wireframe_metadata = context.get("wireframe_metadata", {})
        wireframe_metadata.update(
            {
                "title": title,
                "description": description,
                "canvas_width": canvas_width,
                "canvas_height": canvas_height,
                "sections": sections,
                "sections_completed": [],
            }
        )

        section_names = [
            s.get("name", f"Section {i + 1}") for i, s in enumerate(sections)
        ]

        return {
            "success": True,
            "message": f"Wireframe plan created with {len(sections)} sections: {', '.join(section_names)}. Now use add_wireframe_section for each section to generate elements.",
            "wireframe_metadata": wireframe_metadata,
            "accumulated_elements": context.get("accumulated_elements", []),
        }, False

    def _handle_add_section(
        self, tool_input: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Handle the add_wireframe_section tool - adds elements for a section.
        """
        section_name = tool_input.get("section_name", "Section")
        elements = tool_input.get("elements", [])

        # Get current accumulated elements
        accumulated = context.get("accumulated_elements", [])
        wireframe_metadata = context.get("wireframe_metadata", {})

        # Convert new elements to Excalidraw format
        try:
            converted_elements = convert_to_excalidraw_elements(elements)
            accumulated.extend(converted_elements)

            # Track completed sections
            sections_completed = wireframe_metadata.get("sections_completed", [])
            sections_completed.append(section_name)
            wireframe_metadata["sections_completed"] = sections_completed

            # Calculate remaining sections
            all_sections = wireframe_metadata.get("sections", [])
            remaining = len(all_sections) - len(sections_completed)

            return {
                "success": True,
                "message": f"Added {len(converted_elements)} elements for '{section_name}'. Total elements: {len(accumulated)}. Sections remaining: {remaining}.",
                "accumulated_elements": accumulated,
                "wireframe_metadata": wireframe_metadata,
            }, False

        except Exception as e:
            return {
                "success": False,
                "message": f"Error adding section '{section_name}': {str(e)}. Please try again with valid element definitions.",
                "accumulated_elements": accumulated,
                "wireframe_metadata": wireframe_metadata,
            }, False

    def _handle_finalize(
        self, tool_input: Dict[str, Any], context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Handle the finalize_wireframe tool - completes the wireframe generation.
        This is a termination tool.
        """
        accumulated = context.get("accumulated_elements", [])
        wireframe_metadata = context.get("wireframe_metadata", {})

        # Optionally add any final elements
        final_elements = tool_input.get("final_elements", [])
        if final_elements:
            try:
                converted = convert_to_excalidraw_elements(final_elements)
                accumulated.extend(converted)
            except Exception as e:
                # Log error but continue - final elements are optional
                pass

        # Update canvas size if provided
        if "canvas_width" in tool_input:
            wireframe_metadata["canvas_width"] = tool_input["canvas_width"]
        if "canvas_height" in tool_input:
            wireframe_metadata["canvas_height"] = tool_input["canvas_height"]

        # Final summary
        if "summary" in tool_input:
            wireframe_metadata["description"] = tool_input.get(
                "summary", wireframe_metadata.get("description", "")
            )

        return {
            "success": True,
            "message": f"Wireframe completed with {len(accumulated)} elements.",
            "accumulated_elements": accumulated,
            "wireframe_metadata": wireframe_metadata,
            "element_count": len(accumulated),
        }, True  # This is a termination tool


# Singleton instance
wireframe_tool_executor = WireframeToolExecutor()
