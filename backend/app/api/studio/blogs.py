"""
Blog Post endpoints - AI-generated comprehensive blog posts.

Educational Note: Blog posts demonstrate agent-based generation with image support:
1. blog_agent_executor orchestrates the generation
2. Claude creates markdown structure and content
3. Gemini generates images for hero and sections
4. Complete package: Markdown + images

Agent Pattern:
- Uses blog_agent_executor for orchestration
- Agent has tools for planning, image generation, and writing
- Multi-step process with intermediate results
- Final output is a complete markdown blog post

Output Structure:
- Markdown file with frontmatter (title, meta_description, etc.)
- Image files for hero and section illustrations
- All files stored in Supabase Storage (studio-outputs bucket)
- ZIP download available for full package

Routes:
- POST /projects/<id>/studio/blog                        - Start generation
- GET  /projects/<id>/studio/blog-jobs/<id>              - Job status
- GET  /projects/<id>/studio/blog-jobs                   - List jobs
- GET  /projects/<id>/studio/blogs/<job_id>/<file>       - Serve file (from Supabase)
- GET  /projects/<id>/studio/blogs/<id>/preview          - Preview markdown
- GET  /projects/<id>/studio/blogs/<id>/download         - Download ZIP
- DELETE /projects/<id>/studio/blog-jobs/<id>            - Delete job
"""
import io
import zipfile
from flask import jsonify, request, current_app, send_file, Response
from app.api.studio import studio_bp
from app.services.studio_services import studio_index_service
from app.services.tool_executors.blog_agent_executor import blog_agent_executor
from app.services.integrations.supabase import storage_service


@studio_bp.route('/projects/<project_id>/studio/blog', methods=['POST'])
def generate_blog_post(project_id: str):
    """
    Start blog post generation via blog agent.

    Request Body:
        - source_id: UUID of the source to generate blog from (required)
        - direction: User's direction/guidance (optional)
        - target_keyword: SEO keyword/phrase to target (optional)
        - blog_type: Category of blog post (optional, default: how_to_guide)

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
        target_keyword = data.get('target_keyword', '')
        blog_type = data.get('blog_type', 'how_to_guide')

        # Validate blog_type
        valid_blog_types = [
            'case_study', 'listicle', 'how_to_guide', 'opinion',
            'product_review', 'news', 'tutorial', 'comparison',
            'interview', 'roundup'
        ]
        if blog_type not in valid_blog_types:
            blog_type = 'how_to_guide'

        # Execute via blog_agent_executor (creates job and launches agent)
        result = blog_agent_executor.execute(
            project_id=project_id,
            source_id=source_id,
            direction=direction,
            target_keyword=target_keyword,
            blog_type=blog_type
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
        current_app.logger.error(f"Error starting blog post generation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start blog post generation: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/blog-jobs/<job_id>', methods=['GET'])
def get_blog_job_status(project_id: str, job_id: str):
    """
    Get the status of a blog post generation job.

    Response:
        - Job object with status, progress, and generated content
    """
    try:
        job = studio_index_service.get_blog_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Blog job {job_id} not found'
            }), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        current_app.logger.error(f"Error getting blog job status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@studio_bp.route('/projects/<project_id>/studio/blog-jobs', methods=['GET'])
def list_blog_jobs(project_id: str):
    """
    List all blog post jobs for a project.

    Query Parameters:
        - source_id: Optional filter by source

    Response:
        - List of blog jobs (newest first)
    """
    try:
        source_id = request.args.get('source_id')
        jobs = studio_index_service.list_blog_jobs(project_id, source_id)

        return jsonify({
            'success': True,
            'jobs': jobs
        })

    except Exception as e:
        current_app.logger.error(f"Error listing blog jobs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@studio_bp.route('/projects/<project_id>/studio/blogs/<job_id>/<filename>', methods=['GET'])
def get_blog_file(project_id: str, job_id: str, filename: str):
    """
    Serve a blog file (markdown or image) from Supabase Storage.

    Response:
        - Markdown file or image file with appropriate headers
    """
    try:
        # Determine mimetype
        if filename.endswith('.md'):
            mimetype = 'text/markdown'
            # Text file - use download_studio_file
            content = storage_service.download_studio_file(
                project_id=project_id,
                job_type="blogs",
                job_id=job_id,
                filename=filename
            )
            if content is None:
                return jsonify({
                    'success': False,
                    'error': f'File not found: {filename}'
                }), 404
            return Response(
                content,
                mimetype=mimetype,
                headers={'Content-Type': f'{mimetype}; charset=utf-8'}
            )
        else:
            # Binary file (image)
            if filename.endswith('.png'):
                mimetype = 'image/png'
            elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
                mimetype = 'image/jpeg'
            else:
                mimetype = 'application/octet-stream'

            file_data = storage_service.download_studio_binary(
                project_id=project_id,
                job_type="blogs",
                job_id=job_id,
                filename=filename
            )
            if file_data is None:
                return jsonify({
                    'success': False,
                    'error': f'File not found: {filename}'
                }), 404

            return send_file(
                io.BytesIO(file_data),
                mimetype=mimetype,
                as_attachment=False
            )

    except Exception as e:
        current_app.logger.error(f"Error serving blog file: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to serve file: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/blogs/<job_id>/preview', methods=['GET'])
def preview_blog_post(project_id: str, job_id: str):
    """
    Serve blog post markdown for preview from Supabase Storage.

    Response:
        - Markdown file content
    """
    try:
        # Get job to find markdown file
        job = studio_index_service.get_blog_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Blog job {job_id} not found'
            }), 404

        markdown_file = job.get('markdown_file')
        if not markdown_file:
            return jsonify({
                'success': False,
                'error': 'Blog post not yet generated'
            }), 404

        # Fetch from Supabase Storage
        content = storage_service.download_studio_file(
            project_id=project_id,
            job_type="blogs",
            job_id=job_id,
            filename=markdown_file
        )

        if content is None:
            return jsonify({
                'success': False,
                'error': f'Markdown file not found: {markdown_file}'
            }), 404

        return Response(
            content,
            mimetype='text/markdown',
            headers={'Content-Type': 'text/markdown; charset=utf-8'}
        )

    except Exception as e:
        current_app.logger.error(f"Error previewing blog post: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to preview blog post: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/blogs/<job_id>/download', methods=['GET'])
def download_blog_post(project_id: str, job_id: str):
    """
    Download blog post as ZIP file (markdown + images) from Supabase Storage.

    Response:
        - ZIP file containing markdown and all images
    """
    try:
        # Get job to find files
        job = studio_index_service.get_blog_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Blog job {job_id} not found'
            }), 404

        markdown_file = job.get('markdown_file')
        if not markdown_file:
            return jsonify({
                'success': False,
                'error': 'Blog post not yet generated'
            }), 404

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add markdown file from Supabase
            markdown_content = storage_service.download_studio_file(
                project_id=project_id,
                job_type="blogs",
                job_id=job_id,
                filename=markdown_file
            )
            if markdown_content:
                zip_file.writestr(markdown_file, markdown_content)

            # Add image files from Supabase
            images = job.get('images', [])
            for image_info in images:
                image_filename = image_info.get('filename')
                if image_filename:
                    image_data = storage_service.download_studio_binary(
                        project_id=project_id,
                        job_type="blogs",
                        job_id=job_id,
                        filename=image_filename
                    )
                    if image_data:
                        zip_file.writestr(f"images/{image_filename}", image_data)

        zip_buffer.seek(0)

        # Generate filename from title
        title = job.get('title', 'blog_post')
        safe_name = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()[:50]
        zip_filename = f"{safe_name}.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading blog post: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to download blog post: {str(e)}'
        }), 500


@studio_bp.route('/projects/<project_id>/studio/blog-jobs/<job_id>', methods=['DELETE'])
def delete_blog_job(project_id: str, job_id: str):
    """
    Delete a blog post job and its files from Supabase Storage.

    Response:
        - Success status
    """
    try:
        # Get job to find files
        job = studio_index_service.get_blog_job(project_id, job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': f'Blog job {job_id} not found'
            }), 404

        # Delete all files for this job from Supabase Storage
        storage_service.delete_studio_job_files(
            project_id=project_id,
            job_type="blogs",
            job_id=job_id
        )

        # Delete job from index
        studio_index_service.delete_blog_job(project_id, job_id)

        return jsonify({
            'success': True,
            'message': f'Blog job {job_id} deleted'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting blog job: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete blog job: {str(e)}'
        }), 500
