"""
Social Post endpoints - Platform-specific social media content.

Educational Note: Social posts demonstrate multi-platform content generation:
1. Claude generates platform-optimized copy
2. Gemini Imagen creates accompanying images
3. Different formats for LinkedIn, Facebook/Instagram, Twitter/X

Platform Optimization:
- LinkedIn: Professional tone, longer format, business insights
- Facebook/Instagram: Engaging visuals, hashtags, call-to-action
- Twitter/X: Concise text, thread-ready, emoji usage

Multi-Modal Pipeline:
1. Analyze topic/source content
2. Generate copy for each platform
3. Create visual descriptions for images
4. Generate images with Gemini Imagen
5. Upload to Supabase Storage
6. Return public URLs

Routes:
- POST /projects/<id>/studio/social-posts                    - Start generation
- GET  /projects/<id>/studio/social-post-jobs/<id>           - Job status
- GET  /projects/<id>/studio/social-post-jobs                - List jobs
- GET  /projects/<id>/studio/social/<job_id>/<file>          - Serve image file (from Supabase)
"""
import io
import uuid
from flask import jsonify, request, current_app, send_file
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.studio_services.social_posts_service import social_posts_service
from app.services.integrations.google.imagen_service import imagen_service
from app.services.integrations.supabase import storage_service
from app.services.background_services.task_service import task_service


@studio_bp.route('/projects/<project_id>/studio/social-posts', methods=['POST'])
def generate_social_posts(project_id: str):
    """
    Start social post generation as a background task.

    Educational Note: Social posts are generated with platform-specific images
    and copy for LinkedIn, Facebook/Instagram, and Twitter/X.

    Request Body:
        - topic: Topic/content to create posts about (required)
        - direction: Optional guidance for the style/focus

    Response:
        - success: Boolean
        - job_id: ID for polling status
        - message: Status message
    """
    try:
        data = request.get_json() or {}

        topic = data.get('topic')
        if not topic:
            return jsonify({
                'success': False,
                'error': 'topic is required'
            }), 400

        direction = data.get('direction', 'Create engaging social media posts for this topic.')

        # Check if Gemini is configured
        if not imagen_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured. Please add it in App Settings.'
            }), 400

        # Create job record
        job_id = str(uuid.uuid4())
        studio_index_service.create_social_post_job(
            project_id=project_id,
            job_id=job_id,
            topic=topic,
            direction=direction
        )

        # Submit background task
        task_service.submit_task(
            task_type="social_posts",
            target_id=job_id,
            callable_func=social_posts_service.generate_social_posts,
            project_id=project_id,
            job_id=job_id,
            topic=topic,
            direction=direction
        )

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Social post generation started',
            'topic': topic
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        current_app.logger.error(f"Error starting social post generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start social post generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social-post-jobs/<job_id>', methods=['GET'])
def get_social_post_job_status(project_id: str, job_id: str):
    """
    Get the status of a social post generation job.

    Response:
        - success: Boolean
        - job: Job record with status, progress, posts (when ready)
    """
    try:
        job = studio_index_service.get_social_post_job(project_id, job_id)

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
        current_app.logger.error(f"Error getting social post job status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get job status: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social-post-jobs', methods=['GET'])
def list_social_post_jobs(project_id: str):
    """
    List all social post jobs for a project.

    Response:
        - success: Boolean
        - jobs: List of job records
    """
    try:
        jobs = studio_index_service.list_social_post_jobs(project_id)

        return jsonify({
            'success': True,
            'jobs': jobs,
            'count': len(jobs)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing social post jobs: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/social/<job_id>/<filename>', methods=['GET'])
def get_social_file(project_id: str, job_id: str, filename: str):
    """
    Serve a social post image file from Supabase Storage.

    Response:
        - Image file (png/jpg) with appropriate headers
    """
    try:
        # Fetch from Supabase Storage
        file_data = storage_service.download_studio_binary(
            project_id=project_id,
            job_type="social_posts",
            job_id=job_id,
            filename=filename
        )

        if file_data is None:
            return jsonify({
                'success': False,
                'error': f'Social image not found: {filename}'
            }), 404

        # Determine mimetype
        mimetype = 'image/png' if filename.endswith('.png') else 'image/jpeg'

        return send_file(
            io.BytesIO(file_data),
            mimetype=mimetype,
            as_attachment=False
        )

    except Exception as e:
        current_app.logger.error(f"Error serving social file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve social file: {str(e)}'
        }), 500
