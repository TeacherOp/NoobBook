"""
Ad Creative endpoints - AI-generated marketing images.

Educational Note: Ad creatives demonstrate AI image generation:
1. Claude generates ad copy and visual descriptions
2. Gemini Imagen creates the actual images
3. Multiple ad variants are generated for A/B testing

Image Generation Pattern:
- Gemini Imagen API takes text prompts
- Returns base64-encoded images
- Images are stored as PNG files
- Multiple sizes generated for different platforms

Background Job Flow:
1. POST /ad-creative creates job, returns job_id
2. ad_creative_service runs in background thread
3. Frontend polls GET /ad-jobs/{job_id} for status
4. When ready, images array contains file URLs

Routes:
- POST /projects/<id>/studio/ad-creative        - Start generation
- GET  /projects/<id>/studio/ad-jobs/<id>       - Job status
- GET  /projects/<id>/studio/ad-jobs            - List jobs
- GET  /projects/<id>/studio/creatives/<job_id>/<file> - Serve image file
- GET  /studio/gemini/status                    - Check Gemini config
"""
import io
import uuid
from flask import g, jsonify, request, current_app, send_file
from app.api.studio import studio_bp
from app.api.studio.logo_utils import resolve_logo
from app.services.studio_services import studio_index_service
from app.services.studio_services.ad_creative_service import ad_creative_service
from app.services.integrations.google.imagen_service import imagen_service
from app.services.integrations.supabase import storage_service
from app.services.background_services.task_service import task_service


@studio_bp.route('/projects/<project_id>/studio/ad-creative', methods=['POST'])
def generate_ad_creative(project_id: str):
    """
    Start ad creative generation as a background task.

    Educational Note: This endpoint is non-blocking:
    1. Creates a job record with status="pending"
    2. Submits background task via task_service
    3. Returns job_id immediately for status polling

    Request Body:
        - product_name: Name of the product to create ads for (required)
        - direction: Optional guidance for the ad style/focus

    Response:
        - success: Boolean
        - job_id: ID for polling status
        - message: Status message
    """
    try:
        data = request.get_json() or {}

        product_name = data.get('product_name')
        if not product_name:
            return jsonify({
                'success': False,
                'error': 'product_name is required'
            }), 400

        direction = data.get('direction', 'Create compelling ad creatives for Facebook and Instagram.')

        # Edit mode: load parent job's prompts as context for refinement
        parent_job_id = data.get('parent_job_id')
        edit_instructions = data.get('edit_instructions')
        previous_prompts = None

        if parent_job_id:
            parent_job = studio_index_service.get_ad_job(project_id, parent_job_id)
            if parent_job and parent_job.get('images'):
                previous_prompts = [
                    {"type": img["type"], "prompt": img["prompt"]}
                    for img in parent_job["images"]
                ]

        # Check if Gemini is configured
        if not imagen_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured. Please add it in Admin Settings.'
            }), 400

        # Resolve logo image bytes (brand icon or image source)
        logo_image_bytes, logo_mime_type = resolve_logo(data, project_id)

        # Create job record
        job_id = str(uuid.uuid4())
        studio_index_service.create_ad_job(
            project_id=project_id,
            job_id=job_id,
            product_name=product_name,
            direction=direction
        )

        # Submit background task
        task_service.submit_task(
            task_type="ad_creative",
            target_id=job_id,
            callable_func=ad_creative_service.generate_ad_creatives,
            project_id=project_id,
            job_id=job_id,
            product_name=product_name,
            direction=direction,
            logo_image_bytes=logo_image_bytes,
            logo_mime_type=logo_mime_type,
            user_id=g.user_id,
            previous_prompts=previous_prompts,
            edit_instructions=edit_instructions
        )

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Ad creative generation started',
            'product_name': product_name
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        current_app.logger.error(f"Error starting ad creative: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start ad creative generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/ad-jobs/<job_id>', methods=['GET'])
def get_ad_job_status(project_id: str, job_id: str):
    """
    Get the status of an ad creative generation job.

    Response:
        - success: Boolean
        - job: Job record with status, progress, images (when ready)
    """
    try:
        job = studio_index_service.get_ad_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Job not found: {job_id}'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting ad job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/ad-jobs', methods=['GET'])
def list_ad_jobs(project_id: str):
    """
    List all ad creative jobs for a project.

    Response:
        - success: Boolean
        - jobs: List of job records
    """
    try:
        jobs = studio_index_service.list_ad_jobs(project_id)

        return jsonify({
            'success': True,
            'jobs': jobs,
            'count': len(jobs)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing ad jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/creatives/<job_id>/<filename>', methods=['GET'])
def get_creative_file(project_id: str, job_id: str, filename: str):
    """
    Serve an ad creative image file from Supabase Storage.

    Response:
        - Image file (png/jpg) with appropriate headers
    """
    try:
        data = storage_service.download_studio_binary(
            project_id, "creatives", job_id, filename
        )

        if not data:
            return jsonify({
                'success': False,
                'error': f'Creative file not found: {filename}'
            }), 404

        mimetype = 'image/png' if filename.endswith('.png') else 'image/jpeg'

        return send_file(io.BytesIO(data), mimetype=mimetype, as_attachment=False)

    except Exception as e:
        current_app.logger.error(f"Error serving creative file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve creative file: {str(e)}'
        }), 500


@studio_bp.route('/studio/gemini/status', methods=['GET'])
def get_gemini_status():
    """
    Check if Gemini (Google AI) is configured.

    Response:
        - configured: Boolean indicating if Gemini API key is set
    """
    try:
        return jsonify({
            'success': True,
            'configured': imagen_service.is_configured()
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error checking Gemini status: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to check Gemini status'
        }), 500
