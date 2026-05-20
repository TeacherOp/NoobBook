"""
Knowledge Base Service - Orchestrates all external knowledge base integrations.

Educational Note: This service acts as the single entry point for all knowledge
base tools (Jira, Notion, GitHub, etc.). It handles:
- Loading tool definitions for configured integrations only
- Calling service methods directly for simple integrations
- Formatting results consistently

This keeps main_chat_service.py clean by centralizing all KB integration logic.
"""
from typing import Dict, Any, List, Callable

from app.config import tool_loader
from app.services.integrations.knowledge_bases.jira import jira_service
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

    # Tool name prefixes for routing.
    # Mixpanel tools are NOT listed here — they live agent-internal under
    # backend/app/services/tools/mixpanel_agent/ and are dispatched by
    # mixpanel_analyzer_agent.run(). The main chat only sees the
    # analyze_mixpanel_agent trigger tool.
    JIRA_TOOLS = ["jira_list_projects", "jira_search_issues", "jira_get_issue", "jira_get_project"]
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
