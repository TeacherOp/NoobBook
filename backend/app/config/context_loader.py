"""
Context Loader - Builds dynamic source and memory context for chat system prompts.

Educational Note: This module creates formatted context blocks for the system prompt:

1. Source Context - List of available sources with IDs, types, and summaries
2. Memory Context - User and project memory for personalization

The context is rebuilt on every message to reflect the current state
(active/inactive sources, new uploads, updated memories).
"""
import logging
from typing import Dict, Any, List, Optional

from app.services.source_services import source_service

logger = logging.getLogger(__name__)


class ContextLoader:
    """
    Loader for building source and memory context for chat prompts.

    Educational Note: This loader is called by main_chat_service
    before each API call to build up-to-date context including:
    - Available sources with metadata
    - User memory (persistent across projects)
    - Project memory (specific to current project)
    """

    def get_active_sources(
        self,
        project_id: str,
        selected_source_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get list of active and ready sources for a project.

        Educational Note: When selected_source_ids is a list, only those sources
        with status "ready" are returned. When None (legacy chats that predate
        per-chat selection), falls back to all ready+active sources for backwards
        compatibility. An empty list [] means explicitly no sources selected.

        Args:
            project_id: The project UUID
            selected_source_ids: Per-chat source selection
                - None = legacy chat, use all ready+active sources
                - [] = explicitly no sources selected
                - [...] = only these sources

        Returns:
            List of source metadata dicts for selected/ready sources
        """
        all_sources = source_service.list_sources(project_id)

        if selected_source_ids is None:
            # Legacy chat (column is NULL) — fall back to global active flag
            return [
                source for source in all_sources
                if source.get("status") == "ready" and source.get("active", False)
            ]

        if not selected_source_ids:
            # Explicitly empty selection
            return []

        # Filter to selected sources that are ready
        selected_set = set(selected_source_ids)
        active_sources = [
            source for source in all_sources
            if source.get("id") in selected_set and source.get("status") == "ready"
        ]

        return active_sources

    def build_source_context(
        self,
        project_id: str,
        selected_source_ids: Optional[List[str]] = None,
    ) -> str:
        """
        Build formatted source context for the system prompt.

        Educational Note: This creates a structured text block that tells
        the AI what sources are available and how to reference them.
        The format is designed to be clear and parseable by the model.

        Args:
            project_id: The project UUID
            selected_source_ids: Per-chat source selection (None = no sources)

        Returns:
            Formatted string to append to system prompt, or empty string if no sources
        """
        active_sources = self.get_active_sources(project_id, selected_source_ids=selected_source_ids)

        if not active_sources:
            return ""

        # Build the context block
        lines = [
            "",
            "## Available Sources",
            "",
            "You have access to the following sources.",
            "",
            "- Use the search_sources tool to retrieve information from embedded sources (documents, links, etc.).",
            "- For CSV sources, use analyze_csv_agent when the user asks questions that require calculations/plots from the CSV data.",
            "- For DATABASE sources, use analyze_database_agent when the user asks questions that require LIVE data from the database (counts, metrics, lists, trends).",
            "- For FRESHDESK sources, use analyze_freshdesk_agent when the user asks questions about support ticket data (trends, metrics, SLA, agent performance, etc.).",
            "- For JIRA sources, use jira_list_projects, jira_search_issues, jira_get_issue, jira_get_project for live Jira queries.",
            "- For MIXPANEL sources, use mixpanel_list_events, mixpanel_query_events, mixpanel_segmentation, mixpanel_list_funnels, mixpanel_query_funnel, mixpanel_retention, mixpanel_events_after (cohort path analysis: 'what do users do after X') for live analytics queries.",
            "",
        ]

        for source in active_sources:
            source_id = source.get("id", "")
            name = source.get("name", "Unknown")
            source_type_field = source.get("type", "unknown")  # Database field is 'type'

            # Get embedding info (contains file_extension and is_embedded)
            embedding_info = source.get("embedding_info", {})
            file_ext = embedding_info.get("file_extension", "")
            is_embedded = embedding_info.get("is_embedded", False)
            embedded_label = "Yes" if is_embedded else "No"

            # Get summary if available
            summary_info = source.get("summary_info", {})
            summary_text = summary_info.get("summary", "")

            # Format source type from type field and extension
            source_type = self._format_source_type(source_type_field.lower(), file_ext)

            lines.append(f"- **{name}**")
            lines.append(f"  - ID: `{source_id}`")
            lines.append(f"  - Type: {source_type}")
            lines.append(f"  - Embedded: {embedded_label}")
            if file_ext == ".csv":
                lines.append("  - Chat tool: analyze_csv_agent (for calculations/plots)")
            if file_ext == ".database":
                lines.append("  - Chat tool: analyze_database_agent (for live SQL queries)")
            if file_ext == ".freshdesk":
                lines.append("  - Chat tool: analyze_freshdesk_agent (for ticket analytics)")
            if file_ext == ".jira":
                lines.append("  - Chat tools: jira_list_projects, jira_search_issues, jira_get_issue, jira_get_project (live API)")
            if file_ext == ".mixpanel":
                lines.append("  - Chat tools: mixpanel_list_events, mixpanel_query_events, mixpanel_segmentation, mixpanel_list_funnels, mixpanel_query_funnel, mixpanel_retention, mixpanel_events_after — use mixpanel_events_after for 'what do users do after X' / cohort path analysis questions (live Query API)")
            if file_ext == ".mcp":
                lines.append("  - Chat tool: search_sources (RAG search over MCP resources)")
            if summary_text:
                lines.append(f"  - Summary: {summary_text}")
            lines.append("")

        lines.append("When answering, pick the correct tool based on the source type (search_sources vs analyze_csv_agent vs analyze_database_agent vs analyze_freshdesk_agent).")
        lines.append("")

        return "\n".join(lines)

    def _format_source_type(self, category: str, file_ext: str) -> str:
        """
        Format a human-readable source type from category and extension.

        Args:
            category: Source category (document, image, audio, link, etc.)
            file_ext: File extension (.pdf, .txt, .mp3, etc.)

        Returns:
            Human-readable type string
        """
        # Map common extensions to readable names
        ext_map = {
            ".pdf": "PDF Document",
            ".docx": "Word Document",
            ".doc": "Word Document",
            ".txt": "Text File",
            ".pptx": "PowerPoint",
            ".ppt": "PowerPoint",
            ".mp3": "Audio (MP3)",
            ".wav": "Audio (WAV)",
            ".m4a": "Audio (M4A)",
            ".png": "Image (PNG)",
            ".jpg": "Image (JPEG)",
            ".jpeg": "Image (JPEG)",
            ".webp": "Image (WebP)",
            ".link": "Web Link",
            ".csv": "CSV Spreadsheet",
            ".research": "Research Document",
            ".database": "Database (Postgres/MySQL)",
            ".freshdesk": "Freshdesk Tickets",
            ".jira": "Jira Projects",
            ".mcp": "MCP Server Resources",
        }

        if file_ext in ext_map:
            return ext_map[file_ext]

        # Fallback to category
        category_map = {
            "document": "Document",
            "image": "Image",
            "audio": "Audio",
            "link": "Web Content",
            "video": "Video",
        }

        return category_map.get(category, category.title())

    def build_memory_context(self, project_id: str, user_id: Optional[str] = None) -> str:
        """
        Build formatted memory context for the system prompt.

        Educational Note: Memory context includes:
        - User memory: Persistent preferences and context across all projects
        - Project memory: Context specific to the current project

        This helps the AI personalize responses and maintain continuity.

        Args:
            project_id: The project UUID

        Returns:
            Formatted string to append to system prompt, or empty string if no memory
        """
        # Lazy import to avoid circular imports:
        # memory_service -> app.config -> context_loader -> memory_service
        from app.services.ai_services.memory_service import memory_service

        user_memory = memory_service.get_user_memory(user_id=user_id) if user_id else memory_service.get_user_memory()
        project_memory = (
            memory_service.get_project_memory(project_id, user_id=user_id)
            if user_id
            else memory_service.get_project_memory(project_id)
        )

        # Return empty if no memory exists
        if not user_memory and not project_memory:
            return ""

        lines = [
            "",
            "## Memory Context",
            "",
        ]

        if user_memory:
            lines.append("### User Memory")
            lines.append(f"{user_memory}")
            lines.append("")

        if project_memory:
            lines.append("### Project Memory")
            lines.append(f"{project_memory}")
            lines.append("")

        return "\n".join(lines)

    def build_mcp_tools_context(self, user_id: Optional[str] = None) -> str:
        """
        Build context about available MCP tools for the system prompt.

        Educational Note: Tells Claude about external MCP tools it can use
        during chat. Includes a safety reminder for destructive actions.
        """
        if not user_id:
            return ""

        try:
            from app.services.integrations.mcp.mcp_tool_service import mcp_tool_service

            tools, _ = mcp_tool_service.get_available_tools(user_id=user_id)
            if not tools:
                return ""

            lines = [
                "",
                "## MCP Tools (External Integrations)",
                "",
                "You have access to external tools from connected MCP servers.",
                "These tools can perform real actions (create tickets, search data, etc.).",
                "Always confirm with the user before performing destructive or irreversible actions.",
                "",
            ]

            for tool in tools:
                name = tool.get("name", "")
                desc = tool.get("description", "")
                lines.append(f"- **{name}**: {desc}")

            lines.append("")
            return "\n".join(lines)

        except Exception as e:
            logger.error("Failed to build MCP tools context: %s", e)
            return ""

    def build_full_context(
        self,
        project_id: str,
        user_id: Optional[str] = None,
        selected_source_ids: Optional[List[str]] = None,
    ) -> str:
        """
        Build complete context including sources, memory, and MCP tools.

        Educational Note: Combines all context types for the system prompt.
        Order: Memory context first (general context), then source context
        (available tools), then MCP tools context (external integrations).

        Args:
            project_id: The project UUID
            selected_source_ids: Per-chat source selection (None = no sources)

        Returns:
            Complete context string to append to system prompt
        """
        parts = []

        # Add memory context first (general personalization)
        memory_context = self.build_memory_context(project_id, user_id=user_id)
        if memory_context:
            parts.append(memory_context)

        # Add source context (available tools)
        source_context = self.build_source_context(project_id, selected_source_ids=selected_source_ids)
        if source_context:
            parts.append(source_context)

        # Add MCP tools context (external integrations)
        mcp_context = self.build_mcp_tools_context(user_id=user_id)
        if mcp_context:
            parts.append(mcp_context)

        return "\n".join(parts)


# Singleton instance
context_loader = ContextLoader()
