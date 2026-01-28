"""
Source CRUD endpoints - core source management.

Educational Note: These endpoints handle the lifecycle of source files:
- List all sources for a project
- Upload new source files (multipart/form-data)
- Get/update/delete individual sources
- Download original files
- Get aggregate statistics

File Upload Flow:
1. Frontend sends multipart/form-data with file
2. We validate file type against allowed extensions
3. File is saved to data/projects/{id}/sources/raw/
4. Source entry created in sources_index.json
5. Background processing triggered automatically

Supported File Types (by category):
- document: .pdf, .docx, .pptx, .txt, .md
- image: .png, .jpg, .jpeg, .webp, .gif
- audio: .mp3, .wav, .m4a, .ogg, .flac
- data: .csv

Routes:
- GET    /projects/<id>/sources          - List all sources
- POST   /projects/<id>/sources          - Upload file
- GET    /projects/<id>/sources/<id>     - Get source details
- PUT    /projects/<id>/sources/<id>     - Update metadata
- DELETE /projects/<id>/sources/<id>     - Delete source
- GET    /projects/<id>/sources/<id>/download - Download file
- GET    /projects/<id>/sources/summary  - Aggregate stats
- GET    /sources/allowed-types          - List allowed extensions
"""
from flask import jsonify, request, current_app, send_file, redirect
from app.api.sources import sources_bp
from app.services.source_services import SourceService

# Initialize service
source_service = SourceService()


@sources_bp.route('/projects/<project_id>/sources', methods=['GET'])
def list_sources(project_id: str):
    """
    List all sources for a project.

    Educational Note: Returns metadata for all uploaded sources,
    sorted by most recent first. Includes processing status so
    UI can show progress indicators.

    Returns:
        {
            "success": true,
            "sources": [...],
            "count": 5
        }
    """
    try:
        sources = source_service.list_sources(project_id)

        return jsonify({
            'success': True,
            'sources': sources,
            'count': len(sources)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing sources: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources', methods=['POST'])
def upload_source(project_id: str):
    """
    Upload a new source file to a project.

    Educational Note: This endpoint demonstrates multipart/form-data handling.
    Files are streamed to disk, not loaded entirely into memory - important
    for large PDFs and audio files.

    Content-Type: multipart/form-data
    Form Fields:
        - file: The source file (required)
        - name: Display name (optional, defaults to filename)
        - description: Description (optional)

    Processing is triggered automatically after upload. Status will be:
    uploaded -> processing -> embedding -> ready

    Returns:
        {
            "success": true,
            "source": { ... source object ... },
            "message": "Source uploaded successfully"
        }
    """
    try:
        # Validate file is in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']

        if not file.filename:
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Get optional fields from form data
        name = request.form.get('name')
        description = request.form.get('description', '')

        # Upload the source (triggers background processing)
        source = source_service.upload_source(
            project_id=project_id,
            file=file,
            name=name,
            description=description
        )

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Source uploaded successfully'
        }), 201

    except ValueError as e:
        # Validation errors (file type not allowed, etc.)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    except Exception as e:
        current_app.logger.error(f"Error uploading source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/<source_id>', methods=['GET'])
def get_source(project_id: str, source_id: str):
    """
    Get a specific source's metadata.

    Educational Note: Returns full metadata including:
    - Basic info (name, description, file type)
    - Processing status and progress
    - Embedding info (if processed)
    - Summary (AI-generated description)

    Returns:
        {
            "success": true,
            "source": { ... full source object ... }
        }
    """
    try:
        source = source_service.get_source(project_id, source_id)

        if not source:
            return jsonify({
                'success': False,
                'error': 'Source not found'
            }), 404

        return jsonify({
            'success': True,
            'source': source
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/<source_id>', methods=['PUT'])
def update_source(project_id: str, source_id: str):
    """
    Update a source's metadata.

    Educational Note: Only metadata can be updated (name, description, active).
    The raw file cannot be modified - delete and re-upload instead.

    The 'active' field controls whether the source is included in RAG searches.
    Inactive sources are kept but excluded from chat context.

    Request Body:
        {
            "name": "New display name",
            "description": "Updated description",
            "active": false  // exclude from searches
        }

    Returns:
        { "success": true, "source": { ... updated ... } }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        source = source_service.update_source(
            project_id=project_id,
            source_id=source_id,
            name=data.get('name'),
            description=data.get('description'),
            active=data.get('active')
        )

        if not source:
            return jsonify({
                'success': False,
                'error': 'Source not found'
            }), 404

        return jsonify({
            'success': True,
            'source': source,
            'message': 'Source updated successfully'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error updating source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/<source_id>', methods=['DELETE'])
def delete_source(project_id: str, source_id: str):
    """
    Delete a source and all associated data.

    Educational Note: This is a HARD delete that removes:
    - Raw file from disk
    - Processed text file
    - All chunks
    - Embeddings from Pinecone
    - Entry from sources_index.json

    There is no undo - consider soft delete (active=false) for recoverable hiding.

    Returns:
        { "success": true, "message": "Source deleted successfully" }
    """
    try:
        deleted = source_service.delete_source(project_id, source_id)

        if not deleted:
            return jsonify({
                'success': False,
                'error': 'Source not found'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Source deleted successfully'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/<source_id>/download', methods=['GET'])
def download_source(project_id: str, source_id: str):
    """
    Download the raw source file.

    Educational Note: Redirects to a signed Supabase Storage URL.
    The signed URL expires after 1 hour for security.

    Returns:
        Redirect to signed download URL
    """
    try:
        source = source_service.get_source(project_id, source_id)

        if not source:
            return jsonify({
                'success': False,
                'error': 'Source not found'
            }), 404

        # Get signed URL from Supabase Storage
        download_url = source_service.get_source_file_url(project_id, source_id)

        if not download_url:
            return jsonify({
                'success': False,
                'error': 'Source file not found in storage'
            }), 404

        # Redirect to the signed URL
        return redirect(download_url)

    except Exception as e:
        current_app.logger.error(f"Error downloading source: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/projects/<project_id>/sources/summary', methods=['GET'])
def get_sources_summary(project_id: str):
    """
    Get aggregate statistics about sources.

    Educational Note: Useful for dashboard displays showing:
    - Total source count
    - Breakdown by category (document, image, audio, etc.)
    - Processing status counts
    - Total storage used

    Returns:
        {
            "success": true,
            "summary": {
                "total_count": 10,
                "by_category": {"document": 5, "image": 3, ...},
                "by_status": {"ready": 8, "processing": 2},
                "total_size_bytes": 15000000
            }
        }
    """
    try:
        summary = source_service.get_sources_summary(project_id)

        return jsonify({
            'success': True,
            'summary': summary
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting sources summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sources_bp.route('/sources/allowed-types', methods=['GET'])
def get_allowed_types():
    """
    Get the list of allowed file types for upload.

    Educational Note: This endpoint helps frontend:
    - Set file input accept attribute
    - Validate before upload
    - Show supported types in UI

    Extensions are grouped by category for easier display.

    Returns:
        {
            "success": true,
            "allowed_extensions": {".pdf": "document", ...},
            "by_category": {
                "document": [".pdf", ".docx", ...],
                "image": [".png", ".jpg", ...],
                ...
            }
        }
    """
    try:
        extensions = source_service.get_allowed_extensions()

        # Group by category for easier frontend use
        by_category = {}
        for ext, category in extensions.items():
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(ext)

        return jsonify({
            'success': True,
            'allowed_extensions': extensions,
            'by_category': by_category
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting allowed types: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
