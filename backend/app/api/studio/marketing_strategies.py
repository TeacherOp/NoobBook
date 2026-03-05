"""
Marketing Strategy Generator endpoints - AI-generated Marketing Strategy Documents.

Educational Note: Marketing Strategy generation demonstrates the agentic loop pattern:
1. Agent plans the document structure (sections to write)
2. Agent writes sections incrementally using write_marketing_section tool
3. Agent signals completion via is_last_section=true flag

Output is Markdown which renders nicely on frontend and can be exported.

Routes:
- POST /projects/<id>/studio/marketing-strategy              - Start generation
- GET  /projects/<id>/studio/marketing-strategy-jobs/<id>    - Job status
- GET  /projects/<id>/studio/marketing-strategy-jobs         - List jobs
- GET  /projects/<id>/studio/marketing-strategies/<id>/preview   - Preview markdown content
- GET  /projects/<id>/studio/marketing-strategies/<id>/download  - Download file (md)
- DELETE /projects/<id>/studio/marketing-strategies/<id>     - Delete marketing strategy
"""
import io
from flask import jsonify, request, current_app, send_file

from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.integrations.supabase import storage_service


@studio_bp.route('/projects/<project_id>/studio/marketing-strategy', methods=['POST'])
def generate_marketing_strategy(project_id: str):
    """
    Start marketing strategy generation (background task).

    Request body:
        {
            "source_id": "source-uuid",
            "direction": "optional user direction/preferences"
        }

    Returns:
        202 Accepted with job_id for polling
    """
    from app.services.ai_agents import marketing_strategy_agent_service
    from app.services.source_services import source_service
    from app.services.background_services.task_service import task_service
    import uuid

    try:
        data = request.get_json()

        # Source is optional — can generate from direction alone
        source_id = data.get('source_id')
        direction = data.get('direction', '')

        # Get source info (if provided)
        source_name = "Direction Only"
        if source_id:
            source = source_service.get_source(project_id, source_id)
            if not source:
                return jsonify({
                    'success': False,
                    'error': 'Source not found'
                }), 404
            source_name = source.get('name', 'Unknown Source')

        # Edit mode: load parent job's document as context for refinement
        parent_job_id = data.get('parent_job_id')
        edit_instructions = data.get('edit_instructions')
        previous_document = None

        if parent_job_id and not edit_instructions:
            return jsonify({
                'success': False,
                'error': 'edit_instructions is required when parent_job_id is provided'
            }), 400

        if parent_job_id:
            parent_job = studio_index_service.get_marketing_strategy_job(project_id, parent_job_id)
            if not parent_job or not parent_job.get('markdown_file'):
                return jsonify({
                    'success': False,
                    'error': 'Parent job not found or has no document to edit'
                }), 404

            # Load the full markdown content from storage
            markdown_content = storage_service.download_studio_file(
                project_id, "marketing_strategies", parent_job_id, parent_job['markdown_file']
            )
            if markdown_content:
                previous_document = {
                    "document_title": parent_job.get("document_title"),
                    "product_name": parent_job.get("product_name"),
                    "sections_written": parent_job.get("sections_written", 0),
                    "markdown_content": markdown_content
                }

        # Create job
        job_id = str(uuid.uuid4())
        job = studio_index_service.create_marketing_strategy_job(
            project_id=project_id,
            job_id=job_id,
            source_id=source_id,
            source_name=source_name,
            direction=direction
        )

        # Start background task using centralized task_service
        task_service.submit_task(
            task_type="marketing_strategy",
            target_id=job_id,
            callable_func=marketing_strategy_agent_service.marketing_strategy_agent_service.generate_marketing_strategy,
            project_id=project_id,
            source_id=source_id,
            job_id=job_id,
            direction=direction,
            previous_document=previous_document,
            edit_instructions=edit_instructions,
        )

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Marketing strategy generation started'
        }), 202  # Accepted

    except Exception as e:
        current_app.logger.error(f"Error starting marketing strategy generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start marketing strategy generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/marketing-strategy-jobs/<job_id>', methods=['GET'])
def get_marketing_strategy_job_status(project_id: str, job_id: str):
    """
    Get status of a marketing strategy generation job.

    Returns:
        Job object with current status, progress, and results if complete
    """
    try:
        job = studio_index_service.get_marketing_strategy_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        current_app.logger.error(f"Error getting marketing strategy job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/marketing-strategy-jobs', methods=['GET'])
def list_marketing_strategy_jobs(project_id: str):
    """
    List all marketing strategy jobs for a project, optionally filtered by source.

    Query params:
        source_id (optional): Filter by source ID

    Returns:
        List of marketing strategy jobs sorted by created_at descending
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_marketing_strategy_jobs(project_id, source_id)

        return jsonify({
            'success': True,
            'jobs': jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing marketing strategy jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/marketing-strategies/<job_id>/preview', methods=['GET'])
def preview_marketing_strategy(project_id: str, job_id: str):
    """
    Preview marketing strategy by returning markdown content.

    Returns:
        JSON with markdown content for rendering on frontend
    """
    try:
        job = studio_index_service.get_marketing_strategy_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        markdown_file = job.get('markdown_file')
        if not markdown_file:
            return jsonify({
                'success': False,
                'error': 'Marketing strategy file not yet generated'
            }), 404

        # Read markdown content from Supabase Storage
        markdown_content = storage_service.download_studio_file(
            project_id, "marketing_strategies", job_id, markdown_file
        )

        if not markdown_content:
            return jsonify({
                'success': False,
                'error': 'Marketing strategy file not found'
            }), 404

        return jsonify({
            'success': True,
            'document_title': job.get('document_title', 'Marketing Strategy Document'),
            'product_name': job.get('product_name'),
            'sections_written': job.get('sections_written', 0),
            'total_sections': job.get('total_sections', 0),
            'markdown_content': markdown_content,
            'status': job.get('status')
        })

    except Exception as e:
        current_app.logger.error(f"Error previewing marketing strategy: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to preview marketing strategy: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/marketing-strategies/<job_id>/download', methods=['GET'])
def download_marketing_strategy(project_id: str, job_id: str):
    """
    Download marketing strategy as markdown file.

    Query params:
        format (optional): 'md' (default) - PDF export can be added later

    Returns:
        Markdown file for download
    """
    try:
        job = studio_index_service.get_marketing_strategy_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        markdown_file = job.get('markdown_file')
        if not markdown_file:
            return jsonify({
                'success': False,
                'error': 'Marketing strategy file not yet generated'
            }), 404

        # Download from Supabase Storage
        markdown_content = storage_service.download_studio_file(
            project_id, "marketing_strategies", job_id, markdown_file
        )

        if not markdown_content:
            return jsonify({
                'success': False,
                'error': 'Marketing strategy file not found'
            }), 404

        # Create safe filename from document title
        document_title = job.get('document_title', 'Marketing Strategy')
        safe_title = "".join(c for c in document_title if c.isalnum() or c in " -_").strip()
        if not safe_title:
            safe_title = "Marketing_Strategy"
        download_filename = f"{safe_title}.md"

        # Return as downloadable file
        return send_file(
            io.BytesIO(markdown_content.encode('utf-8')),
            mimetype='text/markdown',
            as_attachment=True,
            download_name=download_filename
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading marketing strategy: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download marketing strategy: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/marketing-strategies/<job_id>', methods=['DELETE'])
def delete_marketing_strategy(project_id: str, job_id: str):
    """
    Delete a marketing strategy and its files.

    Returns:
        Success status
    """
    try:
        # Get job to verify it exists
        job = studio_index_service.get_marketing_strategy_job(project_id, job_id)
        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        # Delete files from Supabase Storage
        storage_service.delete_studio_job_files(project_id, "marketing_strategies", job_id)

        # Delete from index
        deleted = studio_index_service.delete_marketing_strategy_job(project_id, job_id)

        return jsonify({
            'success': deleted,
            'message': 'Marketing strategy deleted' if deleted else 'Failed to delete from index'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting marketing strategy: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete marketing strategy: {str(e)}'
        }), 500
