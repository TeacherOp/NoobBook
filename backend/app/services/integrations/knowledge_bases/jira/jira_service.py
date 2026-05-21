"""
Jira Integration Service - Jira API integration for NoobBook.

Educational Note: This service provides methods to query Jira projects and issues
using the Jira REST API v3. It follows NoobBook's service pattern with lazy-loaded
client initialization and environment-based configuration.
"""
import logging
import os
import time as _time
from typing import Dict, Any, Optional, List
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class JiraService:
    """
    Jira API integration service.

    Educational Note: Singleton pattern with lazy client initialization.
    Configuration is read from environment variables on first use.
    """

    def __init__(self):
        """Initialize the Jira service with lazy-loaded configuration."""
        self._auth = None
        self._base_url = None
        self._configured = None  # Cache configuration check

    def _load_config(self) -> None:
        """
        Lazy-load Jira configuration from environment variables.

        Educational Note: Supports both old and new Jira API formats:
        - Old: https://your-company.atlassian.net/rest/api/3
        - New: https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3

        If JIRA_CLOUD_ID is provided, uses the new centralized gateway format.
        Otherwise, falls back to the legacy direct domain format.
        """
        if self._configured is not None:
            return  # Already loaded

        # Read configuration
        jira_domain = os.getenv('JIRA_DOMAIN', '').rstrip('/')
        jira_email = os.getenv('JIRA_EMAIL')
        jira_api_key = os.getenv('JIRA_API_KEY', '').strip('"')
        jira_cloud_id = os.getenv('JIRA_CLOUD_ID', '').strip()

        # Determine base URL format
        if jira_cloud_id:
            # New centralized gateway format (API tokens with scopes)
            self._base_url = f"https://api.atlassian.com/ex/jira/{jira_cloud_id}/rest/api/3"
            config_label = f"Atlassian API Gateway (Cloud ID: {jira_cloud_id[:8]}...)"
        elif jira_domain:
            # Legacy direct domain format (old API tokens)
            if not jira_domain.startswith('http'):
                jira_domain = f"https://{jira_domain}"
            self._base_url = f"{jira_domain}/rest/api/3"
            config_label = jira_domain
        else:
            self._base_url = None
            config_label = None

        # Auth remains the same for both formats (Basic Auth with email + token)
        self._auth = HTTPBasicAuth(jira_email, jira_api_key) if jira_email and jira_api_key else None

        # Set configured flag
        self._configured = bool(self._base_url and self._auth)

        if self._configured:
            logger.info("Jira service configured: %s", config_label)

    def reload_config(self) -> None:
        """Reset cached config so next call re-reads from environment."""
        self._configured = None

    def is_configured(self) -> bool:
        """Check if Jira credentials are configured."""
        self._load_config()
        return self._configured

    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Jira API.

        Args:
            endpoint: API endpoint (relative to base_url)
            method: HTTP method (GET or POST)
            params: Query parameters
            json_data: JSON body for POST requests

        Returns:
            Dict with 'success' flag and either 'data' or 'error'
        """
        self._load_config()

        if not self.is_configured():
            return {
                "success": False,
                "error": "Jira not configured. Please add JIRA_EMAIL, JIRA_API_KEY, and either JIRA_CLOUD_ID (new) or JIRA_DOMAIN (legacy) to .env"
            }

        call_t0 = _time.monotonic()
        try:
            url = f"{self._base_url}/{endpoint}"
            headers = {'Accept': 'application/json'}

            if method == 'GET':
                response = requests.get(url, auth=self._auth, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, auth=self._auth, headers=headers, json=json_data, timeout=30)
            else:
                return {"success": False, "error": f"Unsupported HTTP method: {method}"}

            # Per-call summary so a Jira issue ("search returns nothing")
            # is debuggable from the bundle alone. Body content isn't
            # logged — only its length.
            log_level = logger.info if response.status_code == 200 else logger.warning
            log_level(
                "JIRA_API endpoint=%s method=%s status=%s ms=%d",
                endpoint, method, response.status_code,
                int((_time.monotonic() - call_t0) * 1000),
            )

            # Handle response codes
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            elif response.status_code == 401:
                return {"success": False, "error": "Authentication failed. Check your JIRA_EMAIL and JIRA_API_KEY"}
            elif response.status_code == 403:
                return {"success": False, "error": "Permission denied. Check your Jira permissions"}
            elif response.status_code == 404:
                return {"success": False, "error": f"Not found: {endpoint}"}
            elif response.status_code == 410:
                return {"success": False, "error": f"API endpoint deprecated: {endpoint}"}
            else:
                return {
                    "success": False,
                    "error": f"Jira API error: {response.status_code} - {response.text[:200]}"
                }

        except requests.exceptions.Timeout:
            logger.warning("JIRA_API endpoint=%s method=%s error=timeout", endpoint, method)
            return {"success": False, "error": "Request timed out. Jira server might be slow or unreachable"}
        except requests.exceptions.ConnectionError:
            logger.warning("JIRA_API endpoint=%s method=%s error=connection", endpoint, method)
            return {"success": False, "error": "Connection failed. Check JIRA_DOMAIN and network connectivity"}
        except Exception as e:
            logger.warning("JIRA_API endpoint=%s method=%s error=%s", endpoint, method, type(e).__name__)
            return {"success": False, "error": f"Request failed: {str(e)}"}

    def list_projects(self, search_query: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        List Jira projects.

        Args:
            search_query: Optional search query to filter projects
            limit: Maximum number of projects to return (default: 50)

        Returns:
            Dict with 'success' flag and either 'projects' list or 'error'
        """
        if search_query:
            # Use project search endpoint
            result = self._make_request(
                'project/search',
                params={'query': search_query, 'maxResults': limit}
            )
            if not result['success']:
                return result

            projects = result['data'].get('values', [])
        else:
            # Get all projects
            result = self._make_request('project', params={'maxResults': limit})
            if not result['success']:
                return result

            data = result['data']
            projects = data if isinstance(data, list) else data.get('values', [])

        # Format project data
        formatted_projects = []
        for project in projects[:limit]:
            formatted_projects.append({
                'key': project.get('key'),
                'name': project.get('name'),
                'description': project.get('description', ''),
                'projectTypeKey': project.get('projectTypeKey'),
                'lead': project.get('lead', {}).get('displayName') if 'lead' in project else None
            })

        return {
            "success": True,
            "projects": formatted_projects,
            "total": len(formatted_projects)
        }

    def get_project(self, project_key: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific project.

        Args:
            project_key: Jira project key (e.g., 'PROJ', 'ENG')

        Returns:
            Dict with 'success' flag and either 'project' dict or 'error'
        """
        if not project_key:
            return {"success": False, "error": "project_key is required"}

        result = self._make_request(f'project/{project_key}')
        if not result['success']:
            return result

        project = result['data']

        # Format detailed project data
        return {
            "success": True,
            "project": {
                'key': project.get('key'),
                'name': project.get('name'),
                'description': project.get('description', ''),
                'lead': project.get('lead', {}).get('displayName') if 'lead' in project else None,
                'projectTypeKey': project.get('projectTypeKey'),
                'issueTypes': [t.get('name') for t in project.get('issueTypes', [])]
            }
        }

    def search_issues(
        self,
        project_key: Optional[str] = None,
        jql: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        issue_type: Optional[str] = None,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """
        Search for Jira issues using JQL or filters.

        Educational Note: Uses Jira's enhanced JQL search API (POST /search/jql)
        which supports pagination and is the recommended endpoint.

        Args:
            project_key: Filter by project (optional)
            jql: Custom JQL query (overrides other filters if provided)
            status: Filter by status (e.g., 'Open', 'In Progress')
            assignee: Filter by assignee username
            issue_type: Filter by issue type (e.g., 'Bug', 'Story')
            max_results: Maximum results to return (default: 50, max: 100)

        Returns:
            Dict with 'success' flag and either 'issues' list or 'error'
        """
        # Cap max_results
        # TODO: Add pagination support to fetch beyond the first page of results
        max_results = min(max_results, 100)

        # Build JQL query if not provided
        if not jql:
            jql_parts = []

            if project_key:
                jql_parts.append(f'project = "{project_key}"')
            if status:
                jql_parts.append(f'status = "{status}"')
            if assignee:
                jql_parts.append(f'assignee = "{assignee}"')
            if issue_type:
                jql_parts.append(f'type = "{issue_type}"')

            jql = ' AND '.join(jql_parts) if jql_parts else 'ORDER BY created DESC'

        # Define fields to retrieve
        fields = [
            'summary', 'status', 'assignee', 'reporter', 'created',
            'updated', 'priority', 'issuetype', 'description'
        ]

        # Build payload for enhanced JQL endpoint
        payload = {
            'jql': jql,
            'fields': fields,
            'maxResults': max_results
        }


        # Use enhanced JQL endpoint
        result = self._make_request('search/jql', method='POST', json_data=payload)
        if not result['success']:
            return result

        # Format issue data
        data = result['data']
        issues = []

        for issue in data.get('issues', []):
            fields_data = issue.get('fields', {})
            issues.append({
                'key': issue.get('key'),
                'summary': fields_data.get('summary'),
                'status': fields_data.get('status', {}).get('name'),
                'type': fields_data.get('issuetype', {}).get('name'),
                'priority': fields_data.get('priority', {}).get('name') if fields_data.get('priority') else None,
                'assignee': fields_data.get('assignee', {}).get('displayName') if fields_data.get('assignee') else 'Unassigned',
                'reporter': fields_data.get('reporter', {}).get('displayName') if fields_data.get('reporter') else 'Unknown',
                'created': fields_data.get('created'),
                'updated': fields_data.get('updated')
            })

        return {
            "success": True,
            "issues": issues,
            "total": len(issues),
            "jql": jql
        }

    def get_issue(self, issue_key: str, include_comments: bool = True) -> Dict[str, Any]:
        """
        Get detailed information about a specific issue.

        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            include_comments: Whether to include comments (default: True)

        Returns:
            Dict with 'success' flag and either 'issue' dict or 'error'
        """
        if not issue_key:
            return {"success": False, "error": "issue_key is required"}

        # Get issue details
        result = self._make_request(f'issue/{issue_key}')
        if not result['success']:
            return result

        issue = result['data']
        fields = issue.get('fields', {})

        # Format description (handle Atlassian Document Format rich text)
        # Limitation: Only extracts text from paragraph > text nodes.
        # Other ADF node types (headings, lists, tables, code blocks, media, etc.)
        # are silently dropped. Expand this if richer extraction is needed.
        description = fields.get('description')
        if isinstance(description, dict):
            content = description.get('content', [])
            text_parts = []
            for block in content:
                if block.get('type') == 'paragraph':
                    for item in block.get('content', []):
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
            description = ' '.join(text_parts)

        issue_data = {
            'key': issue.get('key'),
            'summary': fields.get('summary'),
            'description': description or '',
            'status': fields.get('status', {}).get('name'),
            'type': fields.get('issuetype', {}).get('name'),
            'priority': fields.get('priority', {}).get('name') if fields.get('priority') else None,
            'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else 'Unassigned',
            'reporter': fields.get('reporter', {}).get('displayName') if fields.get('reporter') else 'Unknown',
            'created': fields.get('created'),
            'updated': fields.get('updated'),
            'project': {
                'key': fields.get('project', {}).get('key'),
                'name': fields.get('project', {}).get('name')
            }
        }

        # Get comments if requested
        if include_comments:
            comments_result = self._make_request(f'issue/{issue_key}/comment')

            if comments_result['success']:
                comments = comments_result['data'].get('comments', [])[:10]  # Limit to 10 comments
                formatted_comments = []

                for comment in comments:
                    body = comment.get('body', '')
                    # Handle ADF rich text format (same paragraph > text limitation as above)
                    if isinstance(body, dict):
                        content = body.get('content', [])
                        text_parts = []
                        for block in content:
                            if block.get('type') == 'paragraph':
                                for item in block.get('content', []):
                                    if item.get('type') == 'text':
                                        text_parts.append(item.get('text', ''))
                        body = ' '.join(text_parts)

                    formatted_comments.append({
                        'author': comment.get('author', {}).get('displayName', 'Unknown'),
                        'created': comment.get('created'),
                        'body': body
                    })

                issue_data['comments'] = formatted_comments
                issue_data['comments_count'] = len(comments_result['data'].get('comments', []))

        return {
            "success": True,
            "issue": issue_data
        }


# Singleton instance
jira_service = JiraService()
