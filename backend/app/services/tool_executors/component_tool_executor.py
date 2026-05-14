"""
Component Tool Executor - Handles tool execution for component agent.

Tool handlers extracted from component_agent_service.py for separation of concerns.
Agent handles orchestration, executor handles tool-specific logic.
"""

import logging
import re
from typing import Dict, Any, Tuple, List
from datetime import datetime

from app.services.integrations.supabase import storage_service
from app.services.studio_services import studio_index_service

logger = logging.getLogger(__name__)


class ComponentToolExecutor:
    """Executes component agent tools."""

    TERMINATION_TOOL = "write_component_code"

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
            context: Execution context (project_id, job_id, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_components":
            brand_colors = context.get("brand_colors")
            result = self._handle_plan(project_id, job_id, tool_input, brand_colors)
            return {"success": True, "message": result}, False

        elif tool_name == "write_component_code":
            result = self._handle_write_code(
                project_id=project_id,
                job_id=job_id,
                tool_input=tool_input,
                logo_info=context.get("logo_info"),
                brand_colors=context.get("brand_colors"),
                iterations=context.get("iterations", 0),
                input_tokens=context.get("input_tokens", 0),
                output_tokens=context.get("output_tokens", 0)
            )
            return result, True  # Termination

        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}, False

    def _handle_plan(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        brand_colors: Dict[str, Any] = None
    ) -> str:
        """
        Handle plan_components tool call.

        Educational Note: Same pattern as email agent — prompt-based reminders
        proved unreliable, so we hard-override the planned color_scheme with
        brand values. The tool result also tells the agent exactly which hex
        values to use in the CSS custom properties.
        """
        component_category = tool_input.get("component_category", "other")
        component_description = tool_input.get("component_description", "")
        variations = tool_input.get("variations", [])


        variation_names = [v.get("variation_name", "Unnamed") for v in variations]
        result = (
            f"Component plan saved successfully. "
            f"Category: {component_category}, "
            f"Variations: {', '.join(variation_names)}"
        )

        # Hard-override planned colors with brand palette
        if brand_colors:
            planned_scheme = tool_input.get("color_scheme", {})
            corrected_scheme = {
                "primary": brand_colors.get("primary", planned_scheme.get("primary", "#000000")),
                "secondary": brand_colors.get("secondary", planned_scheme.get("secondary", "#666666")),
                "accent": brand_colors.get("accent", planned_scheme.get("accent", "#0066CC")),
                "background": brand_colors.get("background", planned_scheme.get("background", "#FFFFFF")),
                "text": brand_colors.get("text", planned_scheme.get("text", "#1A1A1A")),
            }
            tool_input["color_scheme"] = corrected_scheme
            result += (
                f" NOTE: Your color_scheme has been corrected to match brand guidelines: "
                f"--primary-color={corrected_scheme['primary']}, "
                f"--secondary-color={corrected_scheme['secondary']}, "
                f"--accent-color={corrected_scheme['accent']}, "
                f"--bg-color={corrected_scheme['background']}, "
                f"--text-color={corrected_scheme['text']}. "
                f"Use these EXACT hex values in the CSS :root variables."
            )

        # Update job with plan (uses corrected color_scheme if brand was active)
        studio_index_service.update_component_job(
            project_id, job_id,
            component_category=component_category,
            component_description=component_description,
            variations_planned=variations,
            color_scheme=tool_input.get("color_scheme"),
            technical_notes=tool_input.get("technical_notes"),
            status_message=f"Planned {len(variations)} variations, generating code..."
        )

        return result

    def _process_brand_in_html(
        self,
        html_code: str,
        logo_info: Dict[str, str] = None,
        brand_colors: Dict[str, Any] = None
    ) -> str:
        """
        Post-process generated HTML to enforce brand assets.

        Educational Note: Even with user-message brand instructions, Claude
        sometimes ignores exact colors or omits the logo. This method provides
        a safety net by directly modifying the HTML output.

        Steps:
        1. Replace BRAND_LOGO placeholder with actual logo URL
        2. Fallback inject logo if agent omitted the placeholder entirely
        3. Override CSS :root variables with brand hex values
        """
        # 1. Replace BRAND_LOGO placeholder with actual URL
        if logo_info:
            logo_url = logo_info["url"]
            html_code = html_code.replace('"BRAND_LOGO"', f'"{logo_url}"')
            html_code = html_code.replace("'BRAND_LOGO'", f"'{logo_url}'")

            # 2. Fallback: inject logo if agent didn't include it at all
            if logo_url not in html_code:
                logo_div = (
                    f'<div style="text-align:center;padding:16px 0;">'
                    f'<img src="{logo_url}" alt="Logo" '
                    f'style="max-height:48px;width:auto;display:inline-block;"></div>'
                )
                body_match = re.search(r'(<body[^>]*>)', html_code, re.IGNORECASE)
                if body_match:
                    insert_pos = body_match.end()
                    html_code = html_code[:insert_pos] + logo_div + html_code[insert_pos:]
                    logger.info("Logo injected (agent omitted BRAND_LOGO placeholder)")
                else:
                    logger.warning("Could not inject brand logo — no <body> tag found")

        # 3. Override CSS :root custom property values with brand colors.
        # Educational Note: The agent might plan correct colors but write
        # different ones in the actual CSS. This regex replaces hex values
        # for known variable names in the :root block as a safety net.
        if brand_colors:
            color_map = {
                "primary-color": brand_colors.get("primary"),
                "secondary-color": brand_colors.get("secondary"),
                "accent-color": brand_colors.get("accent"),
                "bg-color": brand_colors.get("background"),
                "text-color": brand_colors.get("text"),
            }
            for var_name, hex_value in color_map.items():
                if hex_value:
                    # Match --var-name: #hex (with optional whitespace)
                    pattern = rf'(--{re.escape(var_name)}\s*:\s*)#[0-9a-fA-F]{{3,8}}'
                    html_code = re.sub(pattern, rf'\g<1>{hex_value}', html_code)

        return html_code

    def _handle_write_code(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        logo_info: Dict[str, str] = None,
        brand_colors: Dict[str, Any] = None,
        iterations: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> Dict[str, Any]:
        """Handle write_component_code tool call (termination)."""
        components = tool_input.get("components", [])
        usage_notes = tool_input.get("usage_notes", "")

        # Belt-and-braces guard. The agent loop in component_agent_service
        # already detects stop_reason == "max_tokens" and bails before we
        # reach here, but a different failure (malformed tool input, schema
        # drift, etc.) could still hand us an empty components array. If
        # that happens, mark the job as error — never as ready — so the
        # frontend doesn't surface a misleading "Components generated
        # successfully" message with nothing to show. See PR investigation
        # of job b6bbe1fd-... for the original silent-failure trace.
        if not components:
            error_msg = (
                "Model returned no components in the termination tool call. "
                "This usually means the output was truncated. Try regenerating, "
                "or simplify the request (fewer variations, shorter HTML)."
            )
            logger.error(
                "write_component_code received empty components for job %s — marking error",
                job_id[:8],
            )
            studio_index_service.update_component_job(
                project_id, job_id,
                status="error",
                error_message=error_msg,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat(),
            )
            return {
                "success": False,
                "error_message": error_msg,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            }

        try:
            # Save each component as HTML file to Supabase Storage
            saved_components = []
            for idx, component in enumerate(components):
                variation_name = component.get("variation_name", f"Variation {idx + 1}")
                html_code = component.get("html_code", "")
                description = component.get("description", "")

                # Apply brand overrides (logo replacement, CSS variable override)
                html_code = self._process_brand_in_html(
                    html_code, logo_info=logo_info, brand_colors=brand_colors
                )

                # Create safe filename
                safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in variation_name)
                safe_name = safe_name.replace(' ', '_').lower()
                filename = f"{safe_name}.html"

                # Upload HTML file to Supabase Storage
                storage_service.upload_studio_file(
                    project_id=project_id,
                    job_type="components",
                    job_id=job_id,
                    filename=filename,
                    content=html_code,
                    content_type="text/html; charset=utf-8"
                )

                # Track component
                saved_components.append({
                    "variation_name": variation_name,
                    "filename": filename,
                    "description": description,
                    "preview_url": f"/api/v1/projects/{project_id}/studio/components/{job_id}/preview/{filename}",
                    "char_count": len(html_code)
                })

            # Get job info for component category
            job = studio_index_service.get_component_job(project_id, job_id)
            component_category = job.get("component_category", "component") if job else "component"
            component_description = job.get("component_description", "") if job else ""

            # Include brand logo in the images list for reference
            all_images = []
            if logo_info:
                all_images.append(logo_info)

            # Update job to ready
            studio_index_service.update_component_job(
                project_id, job_id,
                status="ready",
                status_message="Components generated successfully!",
                components=saved_components,
                images=all_images,
                usage_notes=usage_notes,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "component_category": component_category,
                "component_description": component_description,
                "components": saved_components,
                "images": all_images,
                "usage_notes": usage_notes,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error writing component code: {str(e)}"
            logger.exception("Failed to write component code")

            studio_index_service.update_component_job(
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
component_tool_executor = ComponentToolExecutor()
