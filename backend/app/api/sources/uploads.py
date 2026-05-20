"""
Alternative source upload endpoints - URL, text, and research.

Educational Note: Not all sources are file uploads. This module handles:

1. URL Sources:
   - Regular websites: Fetched via web agent with web_fetch tool
   - YouTube videos: Transcripts fetched via youtube-transcript-api
   - Stored as .link files in Supabase Storage containing JSON with URL and metadata

2. Text Sources:
   - Pasted text content
   - Stored as .txt files
   - Useful for quick notes, meeting transcripts, etc.

3. Research Sources:
   - AI-generated research on a topic
   - Uses web search to gather information
   - Long-running async operation

Why Different Source Types?
- Files: User has the content locally
- URLs: Content lives on the web
- Text: Quick paste without creating a file
- Research: AI generates content based on topic

Each type goes through the same processing pipeline after creation:
extract -> chunk -> embed -> ready for RAG

Routes:
- POST /projects/<id>/sources/url      - Add website/YouTube source
- POST /projects/<id>/sources/text     - Add pasted text source
- POST /projects/<id>/sources/research - Add AI research source
- POST /projects/<id>/sources/database - Add database source (Postgres/MySQL)
- POST /projects/<id>/sources/mcp      - Add MCP source (external data via MCP servers)
"""
from flask import jsonify, request, current_app
from app.api.sources import sources_bp
from app.services.source_services import SourceService
from app.services.auth.rbac import get_request_identity
from app.services.auth import require_permission
from app.utils.error_responses import error_response

# Initialize service
source_service = SourceService()


@sources_bp.route('/projects/<project_id>/sources/url', methods=['POST'])
@require_permission("document_sources", "url_youtube")
def add_url_source(project_id: str):
    """
    Add a URL source (website or YouTube link) to a project.

    Educational Note: URL sources demonstrate the web agent pattern:
    1. URL is stored as a .link file
    2. Web agent is triggered with web_fetch/web_search tools
    3. Agent extracts relevant content from the page
    4. Extracted text is processed like any other source

    For YouTube:
    - youtube-transcript-api fetches available transcripts
    - Falls back to auto-generated captions if no manual transcript
    - Much faster than web agent (no AI needed)

    Request Body:
        {
            "url": "https://example.com/article",  # required
            "name": "Article Title",                # optional
            "description": "About this article"    # optional
        }

    Returns:
        {
            "success": true,
            "source": { ... source object with status: "uploaded" ... },
            "message": "URL source added successfully"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        url = data.get('url')
        if not url:
            return jsonify({
                'success': False,
                'error': 'URL is required'
            }), 400

        source = source_service.add_url_source(
            project_id=project_id,
            url=url,
            name=data.get('name'),
            description=data.get('description', '')
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'URL source added successfully'
        }), 201

    except ValueError as e:
        # Validation errors (invalid URL, etc.)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        current_app.logger.error(f"Error adding URL source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/text', methods=['POST'])
@require_permission("document_sources", "text")
def add_text_source(project_id: str):
    """
    Add a pasted text source to a project.

    Educational Note: Text sources are the simplest source type:
    1. Text is saved directly as a .txt file
    2. No extraction needed - text is already plain
    3. Goes straight to chunking and embedding

    Use cases:
    - Meeting notes pasted from another app
    - Code snippets
    - Email content
    - Quick notes

    Request Body:
        {
            "content": "The text content to store...",  # required
            "name": "Meeting Notes 2024-01-15",        # required
            "description": "Weekly team sync notes"    # optional
        }

    Returns:
        {
            "success": true,
            "source": { ... source object ... },
            "message": "Text source added successfully"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        content = data.get('content')
        name = data.get('name')

        if not content:
            return jsonify({
                'success': False,
                'error': 'Content is required'
            }), 400

        if not name:
            return jsonify({
                'success': False,
                'error': 'Name is required'
            }), 400

        source = source_service.add_text_source(
            project_id=project_id,
            content=content,
            name=name,
            description=data.get('description', '')
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Text source added successfully'
        }), 201

    except ValueError as e:
        # Validation errors (empty content, etc.)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        current_app.logger.error(f"Error adding text source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/research', methods=['POST'])
def add_research_source(project_id: str):
    """
    Add a deep research source to a project.

    Educational Note: Research sources demonstrate autonomous AI agents:
    1. User provides topic and focus areas
    2. AI agent uses web_search to find relevant sources
    3. Agent synthesizes information into a research document
    4. Document is processed like any other text source

    This is a LONG-RUNNING operation:
    - Can take several minutes depending on topic complexity
    - Status updates: uploaded -> processing -> embedding -> ready
    - Frontend should poll for status updates

    Request Body:
        {
            "topic": "Quantum Computing Applications",    # required
            "description": "Focus on cryptography and...", # required (min 50 chars)
            "links": ["https://reference1.com", ...]      # optional seed URLs
        }

    Returns:
        {
            "success": true,
            "source": { ... source with status: "uploaded" ... },
            "message": "Research source created - processing will begin shortly"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        topic = data.get('topic')
        description = data.get('description')

        if not topic:
            return jsonify({
                'success': False,
                'error': 'Topic is required'
            }), 400

        if not description:
            return jsonify({
                'success': False,
                'error': 'Description is required'
            }), 400

        source = source_service.add_research_source(
            project_id=project_id,
            topic=topic,
            description=description,
            links=data.get('links', [])
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Research source created - processing will begin shortly'
        }), 201

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        current_app.logger.error(f"Error adding research source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/database', methods=['POST'])
@require_permission("data_sources", "database")
def add_database_source(project_id: str):
    """
    Add a database source (Postgres/MySQL) to a project.

    Educational Note: Database sources are connected at the account level
    (settings/databases) and then attached to projects as sources.

    Request Body:
        {
            "connection_id": "uuid",        # required
            "name": "Analytics DB",         # optional display name
            "description": "Read-only..."   # optional
        }
    """
    try:
        identity = get_request_identity()
        data = request.get_json() or {}

        connection_id = data.get('connection_id')
        if not connection_id:
            return jsonify({'success': False, 'error': 'connection_id is required'}), 400

        source = source_service.add_database_source(
            project_id=project_id,
            connection_id=connection_id,
            name=data.get('name'),
            description=data.get('description', ''),
            user_id=identity.user_id,
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Database source added successfully'
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return error_response(e, default_log="Error adding database source")


@sources_bp.route('/projects/<project_id>/sources/freshdesk', methods=['POST'])
@require_permission("data_sources", "freshdesk")
def add_freshdesk_source_endpoint(project_id: str):
    """
    Add a Freshdesk ticket source to a project.

    Educational Note: Freshdesk sources sync ticket data from a configured
    Freshdesk account into a local table for fast SQL-based analysis.
    Credentials come from .env (FRESHDESK_API_KEY, FRESHDESK_DOMAIN).

    Request Body:
        {
            "name": "Support Tickets",   # optional display name
            "description": "Q1 tickets", # optional
            "days_back": 90              # optional, default 90
        }
    """
    try:
        data = request.get_json() or {}

        source = source_service.add_freshdesk_source(
            project_id=project_id,
            name=data.get('name'),
            description=data.get('description', ''),
            days_back=data.get('days_back', 90),
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Freshdesk source added successfully'
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding Freshdesk source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _run_freshdesk_sync(project_id: str, source_id: str, mode: str, days_back: int, clear_first: bool = False):
    """
    Background worker for Freshdesk sync/backfill.
    Educational Note: Tickets are stored globally — clear_first deletes ALL
    tickets (not just for this source) since there's one shared pool.
    """
    from app.services.integrations.freshdesk.freshdesk_sync_service import freshdesk_sync_service
    from app.services.source_services import source_service

    try:
        if clear_first:
            from app.services.integrations.supabase import get_supabase
            # Clear ALL global tickets (not scoped to source_id)
            get_supabase().table("freshdesk_tickets").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

        source_service.update_source(project_id, source_id, status="processing",
                                     processing_info={"syncing": True, "mode": mode, "tickets_fetched": 0})

        stats = freshdesk_sync_service.sync_tickets(
            project_id=project_id, source_id=source_id, mode=mode, days_back=days_back,
        )

        # Get global ticket count
        ticket_stats = freshdesk_sync_service.get_sync_stats()

        source_service.update_source(project_id, source_id, status="ready",
                                     processing_info={
                                         "syncing": False,
                                         "last_sync_mode": mode,
                                         "tickets_fetched": stats.get("tickets_fetched", 0),
                                         "tickets_synced": ticket_stats.get("ticket_count", 0),
                                     })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Freshdesk sync failed: %s", e)
        from app.services.source_services import source_service
        source_service.update_source(project_id, source_id, status="ready",
                                     processing_info={"syncing": False, "error": str(e)})


@sources_bp.route('/projects/<project_id>/sources/<source_id>/freshdesk-sync', methods=['POST'])
def sync_freshdesk_source(project_id: str, source_id: str):
    """Trigger an incremental sync as a background task (shows progress in ActiveTasksBar)."""
    try:
        from app.services.integrations.freshdesk.freshdesk_service import freshdesk_service
        if not freshdesk_service.is_configured():
            return jsonify({'success': False, 'error': 'Freshdesk not configured. Add API key and domain in Settings.'}), 400

        from app.services.background_services import task_service

        data = request.get_json(silent=True) or {}
        mode = data.get('mode', 'incremental')
        days_back = data.get('days_back', 90)

        task_service.submit_task(
            "freshdesk_sync", source_id,
            _run_freshdesk_sync,
            project_id, source_id, mode, days_back,
        )

        return jsonify({
            'success': True,
            'message': f'Freshdesk {mode} sync started'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error syncing Freshdesk source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/projects/<project_id>/sources/<source_id>/freshdesk-backfill', methods=['POST'])
def backfill_freshdesk_source(project_id: str, source_id: str):
    """Clear all tickets and re-fetch last 90 days as a background task."""
    try:
        from app.services.integrations.freshdesk.freshdesk_service import freshdesk_service
        if not freshdesk_service.is_configured():
            return jsonify({'success': False, 'error': 'Freshdesk not configured. Add API key and domain in Settings.'}), 400

        from app.services.background_services import task_service

        task_service.submit_task(
            "freshdesk_backfill", source_id,
            _run_freshdesk_sync,
            project_id, source_id, "backfill", 90, True,
        )

        return jsonify({
            'success': True,
            'message': 'Freshdesk backfill started'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error backfilling Freshdesk source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/projects/<project_id>/sources/jira', methods=['POST'])
@require_permission("data_sources", "jira")
def add_jira_source_endpoint(project_id: str):
    """
    Add a Jira source (live API flag) to a project.

    Educational Note: Jira sources are lightweight flags that enable the
    existing Jira API tools (jira_list_projects, jira_search_issues, etc.)
    per-project. No data is synced locally — all queries go to the live API.

    Request Body:
        {
            "name": "Jira Projects",    # optional display name
            "description": "Our Jira"   # optional
        }
    """
    try:
        data = request.get_json() or {}

        source = source_service.add_jira_source(
            project_id=project_id,
            name=data.get('name'),
            description=data.get('description', ''),
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Jira source added successfully'
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding Jira source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/projects/<project_id>/sources/mixpanel', methods=['POST'])
@require_permission("data_sources", "mixpanel")
def add_mixpanel_source_endpoint(project_id: str):
    """
    Add a Mixpanel source (live API flag) to a project.

    Educational Note: Mixpanel sources are lightweight flags that enable the
    Mixpanel chat tools (mixpanel_list_events, mixpanel_query_events, etc.)
    for this specific project. No data is synced locally — all queries hit
    the Mixpanel Query API live using the globally-configured Service Account.

    Request Body:
        {
            "name": "Mixpanel Analytics",   # optional display name
            "description": "Our Mixpanel"   # optional
        }
    """
    try:
        data = request.get_json() or {}

        source = source_service.add_mixpanel_source(
            project_id=project_id,
            name=data.get('name'),
            description=data.get('description', ''),
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Mixpanel source added successfully'
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding Mixpanel source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/projects/<project_id>/sources/mcp', methods=['POST'])
def add_mcp_source(project_id: str):
    """
    Add an MCP source (external data via MCP server) to a project.

    Educational Note: MCP sources are connected at the account level
    (settings/mcp) and then attached to projects. Users select which
    resources to snapshot, and the content is embedded for RAG search.

    Request Body:
        {
            "connection_id": "uuid",              # required
            "resource_uris": ["uri1", "uri2"],    # required
            "name": "GitHub Docs",                # optional display name
            "description": "Repository docs..."   # optional
        }
    """
    try:
        identity = get_request_identity()
        data = request.get_json() or {}

        connection_id = data.get('connection_id')
        if not connection_id:
            return jsonify({'success': False, 'error': 'connection_id is required'}), 400

        resource_uris = data.get('resource_uris', [])
        if not resource_uris:
            return jsonify({'success': False, 'error': 'resource_uris is required (non-empty list)'}), 400

        source = source_service.add_mcp_source(
            project_id=project_id,
            connection_id=connection_id,
            resource_uris=resource_uris,
            name=data.get('name'),
            description=data.get('description', ''),
            user_id=identity.user_id,
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'MCP source added successfully'
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding MCP source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Notion: picker endpoints + source creation
#
# The picker endpoints (status, search) are project-agnostic — they just expose
# the globally-configured Notion workspace so the frontend can let users browse
# and pick a page/database. The actual source creation is per-project.
# ---------------------------------------------------------------------------


@sources_bp.route('/notion/status', methods=['GET'])
@require_permission("integrations", "notion")
def notion_status():
    """Report whether the global Notion integration is configured."""
    try:
        from app.services.integrations.knowledge_bases.notion.notion_service import (
            notion_service,
        )
        return jsonify({
            'success': True,
            'configured': notion_service.is_configured(),
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error checking Notion status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/notion/search', methods=['GET'])
@require_permission("integrations", "notion")
def notion_search():
    """
    Search the connected Notion workspace for pages and/or databases.

    Query params:
        q: Optional search query (Notion does substring/title matching)
        type: Optional filter — 'page' or 'database' (default: both)
        limit: Optional max results (default: 50, max: 100)
    """
    try:
        from app.services.integrations.knowledge_bases.notion.notion_service import (
            notion_service,
        )

        if not notion_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'Notion not configured. Add NOTION_API_KEY in Settings → API Keys.',
                'configured': False,
            }), 400

        query = request.args.get('q', '').strip() or None
        filter_type = request.args.get('type', '').strip().lower() or None
        if filter_type and filter_type not in ('page', 'database'):
            return jsonify({'success': False, 'error': "type must be 'page' or 'database'"}), 400
        try:
            limit = int(request.args.get('limit', '50'))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 100))

        result = notion_service.search(query=query, filter_type=filter_type, limit=limit)
        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', 'Notion search failed')}), 502

        return jsonify({
            'success': True,
            'results': result.get('results', []),
            'total': result.get('total', 0),
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error searching Notion: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/projects/<project_id>/sources/notion', methods=['POST'])
@require_permission("integrations", "notion")
def add_notion_source_endpoint(project_id: str):
    """
    Add a Notion source (one page or one database) to a project.

    Request Body:
        {
            "notion_id": "uuid",                # required
            "object_type": "page" | "database", # required
            "title": "Picked title",            # optional, from picker
            "notion_url": "https://notion.so/…",# optional
            "last_edited_time": "ISO ts",       # optional
            "name": "Override display name",    # optional
            "description": "..."                # optional
        }
    """
    try:
        data = request.get_json() or {}
        notion_id = (data.get('notion_id') or '').strip()
        object_type = (data.get('object_type') or '').strip().lower()

        if not notion_id:
            return jsonify({'success': False, 'error': 'notion_id is required'}), 400
        if object_type not in ('page', 'database'):
            return jsonify({
                'success': False,
                'error': "object_type must be 'page' or 'database'",
            }), 400

        source = source_service.add_notion_source(
            project_id=project_id,
            notion_id=notion_id,
            object_type=object_type,
            title=data.get('title'),
            notion_url=data.get('notion_url'),
            last_edited_time=data.get('last_edited_time'),
            name=data.get('name'),
            description=data.get('description', ''),
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Notion source added successfully',
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding Notion source: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
