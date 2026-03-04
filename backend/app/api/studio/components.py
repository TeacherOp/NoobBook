"""
Component Generation endpoints - Reusable UI components.

Educational Note: Components demonstrate code generation patterns:
1. component_agent_executor orchestrates generation
2. Claude creates self-contained HTML components
3. Components include inline CSS and JavaScript
4. Ready for copy-paste into any project

Component Pattern:
- Single HTML file per component
- All styles inline or in <style> tags
- JavaScript in <script> tags
- No external dependencies

Use Cases:
- Hero sections from product descriptions
- Feature cards from feature lists
- Testimonial sections from reviews
- Pricing tables from pricing data

Routes:
- POST /projects/<id>/studio/components                      - Start generation
- GET  /projects/<id>/studio/component-jobs/<id>             - Job status
- GET  /projects/<id>/studio/component-jobs                  - List jobs
- GET  /projects/<id>/studio/components/<id>/preview/<file>  - Preview HTML
"""
import io
from flask import g, jsonify, request, current_app, send_file, Response
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.tool_executors.component_agent_executor import component_agent_executor
from app.services.integrations.supabase import storage_service


@studio_bp.route('/projects/<project_id>/studio/components', methods=['POST'])
def generate_components(project_id: str):
    """
    Start component generation via component agent.

    Request Body:
        - source_id: UUID of the source to generate components from (required)
        - direction: User's direction/guidance (optional)

    Response:
        - 202 Accepted with job_id for polling
    """
    try:
        data = request.get_json()

        # Validate input
        source_id = data.get('source_id')
        if not source_id:
            return jsonify({
                'success': False,
                'error': 'source_id is required'
            }), 400

        direction = data.get('direction', '')

        # Edit mode: load parent job's component data as context for refinement
        parent_job_id = data.get('parent_job_id')
        edit_instructions = data.get('edit_instructions')
        previous_components = None

        if parent_job_id and not edit_instructions:
            return jsonify({
                'success': False,
                'error': 'edit_instructions is required when parent_job_id is provided'
            }), 400

        if parent_job_id:
            parent_job = studio_index_service.get_component_job(project_id, parent_job_id)
            if parent_job and parent_job.get('components'):
                previous_components = {
                    "component_category": parent_job.get("component_category"),
                    "component_description": parent_job.get("component_description"),
                    "variations": [
                        {"variation_name": c["variation_name"], "description": c["description"]}
                        for c in parent_job["components"]
                    ]
                }
            else:
                return jsonify({
                    'success': False,
                    'error': 'Parent job not found or has no components to edit'
                }), 404

        # Execute via component_agent_executor (creates job and launches agent)
        result = component_agent_executor.execute(
            project_id=project_id,
            source_id=source_id,
            direction=direction,
            user_id=g.user_id,
            previous_components=previous_components,
            edit_instructions=edit_instructions
        )

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify({
            'success': True,
            'job_id': result['job_id'],
            'status': result['status'],
            'message': result['message']
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error starting component generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start component generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/component-jobs/<job_id>', methods=['GET'])
def get_component_job_status(project_id: str, job_id: str):
    """
    Get the status of a component generation job.

    Response:
        - Job object with status, progress, and generated components
    """
    try:
        job = studio_index_service.get_component_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Component job {job_id} not found'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        current_app.logger.error(f"Error getting component job status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@studio_bp.route('/projects/<project_id>/studio/component-jobs', methods=['GET'])
def list_component_jobs(project_id: str):
    """
    List all component generation jobs for a project.

    Query Parameters:
        - source_id: Optional filter by source

    Response:
        - List of component jobs (newest first)
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_component_jobs(project_id, source_id)

        return jsonify({
            'success': True,
            'jobs': jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing component jobs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@studio_bp.route('/projects/<project_id>/studio/components/<job_id>/preview/<filename>', methods=['GET'])
def preview_component(project_id: str, job_id: str, filename: str):
    """
    Serve component HTML for preview (iframe).

    Response:
        - HTML file for rendering in iframe
    """
    try:
        # Download from Supabase Storage
        content = storage_service.download_studio_file(
            project_id, "components", job_id, filename
        )
        if content is None:
            return jsonify({
                'success': False,
                'error': f'Component file not found: {filename}'
            }), 404

        return Response(content, mimetype='text/html')

    except Exception as e:
        current_app.logger.error(f"Error serving component preview: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve component: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/components/<job_id>/assets/<filename>', methods=['GET'])
def serve_component_asset(project_id: str, job_id: str, filename: str):
    """
    Serve a non-HTML asset (logo, image) from a component job directory.

    Educational Note: The preview route hardcodes mimetype='text/html' for
    iframe rendering. This route serves other file types (brand logos, images)
    that are referenced by the generated HTML components.
    """
    try:
        # Download binary from Supabase Storage
        file_data = storage_service.download_studio_binary(
            project_id, "components", job_id, filename
        )
        if file_data is None:
            return jsonify({
                'success': False,
                'error': f'Asset not found: {filename}'
            }), 404

        # Determine mimetype from extension
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        mimetypes_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'svg': 'image/svg+xml',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'ico': 'image/x-icon',
        }
        mimetype = mimetypes_map.get(ext, 'application/octet-stream')

        return send_file(io.BytesIO(file_data), mimetype=mimetype, as_attachment=False)

    except Exception as e:
        current_app.logger.error(f"Error serving component asset: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to serve asset'
        }), 500
