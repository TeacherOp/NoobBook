"""
Knowledge Base Service - Orchestrates all external knowledge base integrations.

Educational Note: This service acts as the single entry point for all knowledge
base tools (Jira, Notion, GitHub, etc.). It handles:
- Loading tool definitions for configured integrations only
- Calling service methods directly for simple integrations
- Formatting results consistently

This keeps main_chat_service.py clean by centralizing all KB integration logic.
"""
from datetime import date, timedelta
from typing import Dict, Any, List, Callable, Tuple

from app.config import tool_loader
from app.services.integrations.knowledge_bases.jira import jira_service
from app.services.integrations.knowledge_bases.mixpanel import mixpanel_service
from app.services.integrations.knowledge_bases.notion import notion_service


class KnowledgeBaseService:
    """
    Orchestrator for all knowledge base integration tools.

    Educational Note: This service checks which integrations are configured
    and dynamically provides only available tools to Claude. For example:
    - If Jira is configured: Adds 4 Jira tools
    - If Notion is configured: Adds Notion tools
    - If GitHub is configured: Adds GitHub tools

    This allows seamless addition of new integrations without touching
    main_chat_service.py.
    """

    # Tool name prefixes for routing
    JIRA_TOOLS = ["jira_list_projects", "jira_search_issues", "jira_get_issue", "jira_get_project"]
    MIXPANEL_TOOLS = [
        "mixpanel_list_events",
        "mixpanel_query_events",
        "mixpanel_segmentation",
        "mixpanel_list_funnels",
        "mixpanel_query_funnel",
        "mixpanel_retention",
        "mixpanel_events_after",
    ]
    NOTION_TOOLS = ["notion_search", "notion_read_page", "notion_get_database_schema", "notion_query_database"]
    GITHUB_TOOLS = []  # Future: ["github_search_prs", "github_get_issue", ...]

    def __init__(self):
        """Initialize the service with lazy-loaded tool definitions and dispatch table."""
        # Single cache for all tool definitions (lazy-loaded)
        self._tool_cache: Dict[str, Dict[str, Any]] = {}

        # Dispatch table: maps tool name -> (executor_method, )
        # Each executor handles calling the service + formatting the result
        self._dispatch: Dict[str, Callable[[Dict[str, Any]], str]] = {
            # Jira tools
            "jira_list_projects": self._execute_jira_list_projects,
            "jira_search_issues": self._execute_jira_search_issues,
            "jira_get_issue": self._execute_jira_get_issue,
            "jira_get_project": self._execute_jira_get_project,
            # Mixpanel tools
            "mixpanel_list_events": self._execute_mixpanel_list_events,
            "mixpanel_query_events": self._execute_mixpanel_query_events,
            "mixpanel_segmentation": self._execute_mixpanel_segmentation,
            "mixpanel_list_funnels": self._execute_mixpanel_list_funnels,
            "mixpanel_query_funnel": self._execute_mixpanel_query_funnel,
            "mixpanel_retention": self._execute_mixpanel_retention,
            "mixpanel_events_after": self._execute_mixpanel_events_after,
            # Notion tools
            "notion_search": self._execute_notion_search,
            "notion_read_page": self._execute_notion_read_page,
            "notion_get_database_schema": self._execute_notion_get_database_schema,
            "notion_query_database": self._execute_notion_query_database,
        }

    def _get_tool(self, tool_name: str) -> Dict[str, Any]:
        """
        Load a tool definition by name (cached).

        All knowledge base tools live in the 'chat_tools' category.
        """
        if tool_name not in self._tool_cache:
            self._tool_cache[tool_name] = tool_loader.load_tool("chat_tools", tool_name)
        return self._tool_cache[tool_name]

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get non-Jira knowledge base tools (Notion, GitHub, etc.).

        Educational Note: Jira tools are now project-scoped — they are only
        added when a project has a .jira source. Use get_jira_tools() for
        Jira-specific tools. This method returns everything else.

        Returns:
            List of tool definitions ready for Claude API
        """
        tools = []

        # Jira tools are intentionally excluded here — they are project-scoped
        # and added via get_jira_tools() only when the project has a .jira source.

        # Add Notion tools if configured
        if notion_service.is_configured():
            tools.extend([self._get_tool(name) for name in self.NOTION_TOOLS])

        # Future: Add GitHub tools if configured
        # if github_service.is_configured():
        #     tools.extend([self._get_tool(name) for name in self.GITHUB_TOOLS])

        return tools

    def get_jira_tools(self) -> List[Dict[str, Any]]:
        """
        Get Jira-specific tools if Jira is configured.

        Educational Note: Jira tools are project-scoped — they are only added
        to the chat tool list when the project has an active .jira source.
        This allows per-project access control via the source flag pattern.

        Returns:
            List of Jira tool definitions, or empty list if not configured
        """
        if jira_service.is_configured():
            return [self._get_tool(name) for name in self.JIRA_TOOLS]
        return []

    def get_mixpanel_tools(self) -> List[Dict[str, Any]]:
        """
        Get Mixpanel-specific tools if Mixpanel is configured.

        Educational Note: Mirrors get_jira_tools — project-scoped. Tools are
        only added to the chat tool list when the project has an active
        .mixpanel source flag.

        Returns:
            List of Mixpanel tool definitions, or empty list if not configured
        """
        if mixpanel_service.is_configured():
            return [self._get_tool(name) for name in self.MIXPANEL_TOOLS]
        return []

    def can_handle(self, tool_name: str) -> bool:
        """
        Check if this service can handle the given tool.

        Args:
            tool_name: The tool name from Claude's response

        Returns:
            True if this service handles the tool
        """
        return tool_name in self._dispatch

    def execute(
        self,
        project_id: str,
        chat_id: str,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """
        Execute a knowledge base tool.

        Educational Note: Uses a dispatch table to route tool calls to the
        appropriate executor. No separate executors needed for simple API
        integrations.

        Args:
            project_id: The project UUID
            chat_id: The chat UUID
            tool_name: Name of the tool to execute
            tool_input: Input parameters from Claude

        Returns:
            Formatted result string for Claude
        """
        executor = self._dispatch.get(tool_name)
        if executor:
            return executor(tool_input)
        return f"Unknown knowledge base tool: {tool_name}"

    # --- Jira formatters ---

    def _execute_jira_list_projects(self, tool_input: Dict[str, Any]) -> str:
        """List Jira projects."""
        search_query = tool_input.get("search_query")
        limit = tool_input.get("limit", 50)

        result = jira_service.list_projects(search_query=search_query, limit=limit)

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        projects = result["projects"]
        lines = [f"Found {result['total']} Jira project(s):", ""]

        for project in projects:
            lines.append(f"**{project['key']}** - {project['name']}")
            if project.get('description'):
                lines.append(f"  Description: {project['description']}")
            if project.get('projectTypeKey'):
                lines.append(f"  Type: {project['projectTypeKey']}")
            if project.get('lead'):
                lines.append(f"  Lead: {project['lead']}")
            lines.append("")

        return "\n".join(lines)

    def _execute_jira_get_project(self, tool_input: Dict[str, Any]) -> str:
        """Get detailed project information."""
        project_key = tool_input.get("project_key")

        if not project_key:
            return "Error: project_key is required"

        result = jira_service.get_project(project_key)

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        project = result["project"]
        lines = [f"# Project: {project['name']} ({project['key']})", ""]

        if project.get('description'):
            lines.append(f"**Description:** {project['description']}")
            lines.append("")

        if project.get('lead'):
            lines.append(f"**Project Lead:** {project['lead']}")
            lines.append("")

        if project.get('projectTypeKey'):
            lines.append(f"**Project Type:** {project['projectTypeKey']}")
            lines.append("")

        if project.get('issueTypes'):
            lines.append("**Available Issue Types:**")
            for issue_type in project['issueTypes']:
                lines.append(f"  - {issue_type}")
            lines.append("")

        return "\n".join(lines)

    def _execute_jira_search_issues(self, tool_input: Dict[str, Any]) -> str:
        """Search for Jira issues."""
        project_key = tool_input.get("project_key")
        jql = tool_input.get("jql")
        status = tool_input.get("status")
        assignee = tool_input.get("assignee")
        issue_type = tool_input.get("issue_type")
        max_results = tool_input.get("max_results", 50)

        result = jira_service.search_issues(
            project_key=project_key,
            jql=jql,
            status=status,
            assignee=assignee,
            issue_type=issue_type,
            max_results=max_results
        )

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        issues = result["issues"]
        lines = [f"Found {result['total']} issue(s) matching query: {result['jql']}", ""]

        if not issues:
            lines.append("No issues found matching the criteria.")
        else:
            for issue in issues:
                lines.append(f"**{issue['key']}** - {issue['summary']}")
                lines.append(f"  Status: {issue.get('status', 'Unknown')}")
                lines.append(f"  Type: {issue.get('type', 'Unknown')}")
                lines.append(f"  Assignee: {issue.get('assignee', 'Unassigned')}")
                if issue.get('priority'):
                    lines.append(f"  Priority: {issue['priority']}")
                lines.append("")

        if issues:
            lines.append(f"Use jira_get_issue with the issue key (e.g., '{issues[0]['key']}') to get detailed information.")

        return "\n".join(lines)

    def _execute_jira_get_issue(self, tool_input: Dict[str, Any]) -> str:
        """Get detailed issue information."""
        issue_key = tool_input.get("issue_key")
        include_comments = tool_input.get("include_comments", True)

        if not issue_key:
            return "Error: issue_key is required (e.g., 'PROJ-123')"

        result = jira_service.get_issue(
            issue_key=issue_key,
            include_comments=include_comments
        )

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        issue = result["issue"]
        lines = [f"# {issue['key']}: {issue['summary']}", ""]

        # Basic info
        lines.append(f"**Status:** {issue.get('status', 'Unknown')}")
        lines.append(f"**Type:** {issue.get('type', 'Unknown')}")
        if issue.get('priority'):
            lines.append(f"**Priority:** {issue['priority']}")
        lines.append(f"**Assignee:** {issue.get('assignee', 'Unassigned')}")
        lines.append(f"**Reporter:** {issue.get('reporter', 'Unknown')}")
        lines.append("")

        # Project info
        if issue.get('project'):
            project = issue['project']
            lines.append(f"**Project:** {project.get('name')} ({project.get('key')})")
            lines.append("")

        # Dates
        lines.append(f"**Created:** {issue.get('created', 'Unknown')}")
        lines.append(f"**Updated:** {issue.get('updated', 'Unknown')}")
        lines.append("")

        # Description
        if issue.get('description'):
            lines.append("## Description")
            lines.append(issue['description'])
            lines.append("")

        # Comments
        if include_comments and issue.get('comments'):
            comments = issue['comments']
            comments_count = issue.get('comments_count', len(comments))
            lines.append(f"## Comments ({len(comments)} shown, {comments_count} total)")
            lines.append("")

            for comment in comments:
                lines.append(f"**{comment['author']}** - {comment['created']}")
                lines.append(comment['body'])
                lines.append("")

        return "\n".join(lines)

    # --- Mixpanel formatters ---

    @staticmethod
    def _default_date_window(tool_input: Dict[str, Any]) -> Tuple[str, str]:
        # Mixpanel Query API requires from_date/to_date. Fall back to yesterday→today
        # so a call still succeeds if the user (and Claude) didn't specify a window.
        today = date.today()
        yesterday = today - timedelta(days=1)
        from_date = tool_input.get("from_date") or yesterday.isoformat()
        to_date = tool_input.get("to_date") or today.isoformat()
        # Guard against an inverted window when only one side is user-supplied
        # (e.g. to_date="2025-01-01" + default from_date=yesterday).
        if from_date > to_date:
            from_date = to_date
        return from_date, to_date

    def _execute_mixpanel_list_events(self, tool_input: Dict[str, Any]) -> str:
        """List tracked event names."""
        limit = tool_input.get("limit", 100)
        result = mixpanel_service.list_events(limit=limit)
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        events = result.get("events", [])
        lines = [f"Found {result['total']} tracked event(s) in Mixpanel:", ""]
        if not events:
            lines.append("No events tracked yet.")
        else:
            for name in events:
                lines.append(f"- {name}")
        return "\n".join(lines)

    def _execute_mixpanel_query_events(self, tool_input: Dict[str, Any]) -> str:
        """Event counts over time."""
        event_names = tool_input.get("event_names") or []
        from_date, to_date = self._default_date_window(tool_input)
        unit = tool_input.get("unit", "day")

        result = mixpanel_service.query_events(
            event_names=event_names,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
        )
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"
        return self._format_mixpanel_data(result.get("data"), title=f"Event counts ({unit}, {from_date} → {to_date})")

    def _execute_mixpanel_segmentation(self, tool_input: Dict[str, Any]) -> str:
        """Segmented event counts."""
        event = tool_input.get("event")
        from_date, to_date = self._default_date_window(tool_input)
        on = tool_input.get("on")
        where = tool_input.get("where")
        unit = tool_input.get("unit", "day")

        result = mixpanel_service.segmentation(
            event=event, from_date=from_date, to_date=to_date,
            on=on, where=where, unit=unit,
        )
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"
        return self._format_mixpanel_data(
            result.get("data"),
            title=f"Segmentation of {event} by {on or '(none)'} ({from_date} → {to_date})",
        )

    def _execute_mixpanel_list_funnels(self, tool_input: Dict[str, Any]) -> str:
        """List funnels."""
        result = mixpanel_service.list_funnels()
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        funnels = result.get("funnels", [])
        lines = [f"Found {result['total']} funnel(s):", ""]
        if not funnels:
            lines.append("No funnels configured in Mixpanel.")
        else:
            for f in funnels:
                lines.append(f"- **{f.get('name', '(unnamed)')}** (funnel_id: {f.get('funnel_id')})")
        return "\n".join(lines)

    def _execute_mixpanel_query_funnel(self, tool_input: Dict[str, Any]) -> str:
        """Funnel conversion."""
        funnel_id = tool_input.get("funnel_id")
        from_date, to_date = self._default_date_window(tool_input)
        unit = tool_input.get("unit", "day")

        result = mixpanel_service.query_funnel(
            funnel_id=funnel_id, from_date=from_date, to_date=to_date, unit=unit,
        )
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"
        return self._format_mixpanel_data(
            result.get("data"),
            title=f"Funnel {funnel_id} ({unit}, {from_date} → {to_date})",
        )

    def _execute_mixpanel_retention(self, tool_input: Dict[str, Any]) -> str:
        """Retention analysis."""
        born_event = tool_input.get("born_event")
        event = tool_input.get("event")
        from_date, to_date = self._default_date_window(tool_input)
        retention_type = tool_input.get("retention_type", "birth")
        unit = tool_input.get("unit", "day")

        result = mixpanel_service.retention(
            born_event=born_event, event=event,
            from_date=from_date, to_date=to_date,
            retention_type=retention_type, unit=unit,
        )
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"
        return self._format_mixpanel_data(
            result.get("data"),
            title=f"Retention: {born_event} → {event or '(any)'} ({retention_type}, {unit})",
        )

    def _execute_mixpanel_events_after(self, tool_input: Dict[str, Any]) -> str:
        """Cohort path analysis — top events users fire after a trigger event."""
        trigger_event = tool_input.get("trigger_event")
        if not trigger_event:
            return "Error: trigger_event is required."
        from_date, to_date = self._default_date_window(tool_input)
        window_hours = tool_input.get("window_hours", 168)
        top_n = tool_input.get("top_n", 20)
        exclude_trigger = tool_input.get("exclude_trigger", True)

        result = mixpanel_service.events_after(
            trigger_event=trigger_event,
            from_date=from_date,
            to_date=to_date,
            window_hours=window_hours,
            top_n=top_n,
            exclude_trigger=exclude_trigger,
        )
        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        # Render as a markdown ranked list — Claude reads markdown lists more
        # cleanly than nested JSON for "top N" questions, and this output is
        # what the user ultimately sees. Mirrors the list-funnel formatter.
        data = result["data"]
        cohort_size = data["cohort_size"]
        top_events = data["top_events"]
        days = round(window_hours / 24, 1)

        if cohort_size == 0:
            return (
                f"No users fired \"{trigger_event}\" between {from_date} and {to_date}. "
                "Try widening the date range or check the event name spelling."
            )

        lines = [
            f"Cohort: {cohort_size:,} users fired \"{trigger_event}\" between "
            f"{from_date} and {to_date}",
            f"Top events fired in the next {days} day(s):",
            "",
        ]
        if not top_events:
            lines.append("(cohort users fired no other events in the window)")
        else:
            for i, row in enumerate(top_events, 1):
                lines.append(
                    f"{i}. **{row['event']}** — "
                    f"{row['users']:,} users ({row['pct_of_cohort']}%)"
                )
        return "\n".join(lines)

    @staticmethod
    def _format_mixpanel_data(data: Any, title: str) -> str:
        """
        Render Mixpanel Query API payload as a compact JSON block Claude can reason over.

        Educational Note: Mixpanel responses have several shapes (events dict,
        segmentation nested dict, funnels list). Rather than hand-format each,
        we emit JSON inside a fenced block — Claude's strong at parsing JSON.
        """
        import json as _json
        try:
            rendered = _json.dumps(data, indent=2, default=str)
        except Exception:
            rendered = str(data)

        # Keep the block small — truncate huge payloads to protect context window
        if len(rendered) > 15000:
            rendered = rendered[:15000] + "\n... (truncated)"

        return f"## {title}\n\n```json\n{rendered}\n```"

    # --- Notion formatters ---

    def _execute_notion_search(self, tool_input: Dict[str, Any]) -> str:
        """Search Notion pages and databases."""
        query = tool_input.get("query")
        filter_type = tool_input.get("filter_type")
        limit = tool_input.get("limit", 20)

        result = notion_service.search(query=query, filter_type=filter_type, limit=limit)

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        results = result["results"]
        lines = [f"Found {result['total']} Notion item(s):", ""]

        if not results:
            lines.append("No results found.")
        else:
            for item in results:
                title = item.get('title', 'Untitled')
                item_type = item.get('type', 'unknown')
                lines.append(f"**{title}** ({item_type})")
                lines.append(f"  ID: {item['id']}")
                lines.append(f"  URL: {item.get('url', 'N/A')}")
                lines.append(f"  Last edited: {item.get('last_edited_time', 'N/A')}")
                lines.append("")

        if results:
            lines.append(f"Use notion_read_page with the ID to read page content, or notion_get_database_schema to see database structure.")

        return "\n".join(lines)

    def _execute_notion_read_page(self, tool_input: Dict[str, Any]) -> str:
        """Read full page content."""
        page_id = tool_input.get("page_id")

        if not page_id:
            return "Error: page_id is required"

        result = notion_service.get_page(page_id)

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        page = result["page"]
        lines = [
            f"# Page Content",
            f"**ID:** {page['id']}",
            f"**URL:** {page['url']}",
            f"**Created:** {page['created_time']}",
            f"**Last edited:** {page['last_edited_time']}",
            "",
            "## Content",
            page.get('content', '(No content)')
        ]

        return "\n".join(lines)

    def _execute_notion_get_database_schema(self, tool_input: Dict[str, Any]) -> str:
        """Get database schema."""
        database_id = tool_input.get("database_id")

        if not database_id:
            return "Error: database_id is required"

        result = notion_service.get_database(database_id)

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        database = result["database"]
        lines = [
            f"# Database: {database['title']}",
            f"**ID:** {database['id']}",
            f"**URL:** {database['url']}",
            "",
            "## Properties:"
        ]

        schema = database.get('schema', {})
        for prop_name, prop_info in schema.items():
            lines.append(f"- **{prop_name}**: {prop_info['type']}")

        lines.append("")
        lines.append("Use notion_query_database with this database_id to retrieve pages/rows.")

        return "\n".join(lines)

    def _execute_notion_query_database(self, tool_input: Dict[str, Any]) -> str:
        """Query database pages."""
        database_id = tool_input.get("database_id")
        filter_conditions = tool_input.get("filter_conditions")
        limit = tool_input.get("limit", 20)

        if not database_id:
            return "Error: database_id is required"

        result = notion_service.query_database(
            database_id=database_id,
            filter_conditions=filter_conditions,
            limit=limit
        )

        if not result["success"]:
            return f"Error: {result.get('error', 'Unknown error')}"

        results = result["results"]
        lines = [f"Found {result['total']} page(s) in database:", ""]

        if not results:
            lines.append("No pages found matching the criteria.")
        else:
            for page in results:
                lines.append(f"**Page ID:** {page['id']}")
                lines.append(f"**URL:** {page['url']}")
                lines.append("**Properties:**")

                properties = page.get('properties', {})
                for prop_name, prop_value in properties.items():
                    if prop_value is not None:
                        lines.append(f"  - {prop_name}: {prop_value}")

                lines.append("")

        return "\n".join(lines)


# Singleton instance
knowledge_base_service = KnowledgeBaseService()
