"""
Message endpoints - the core AI interaction.

Educational Note: This is where the magic happens! When a user sends a message,
the main_chat_service orchestrates:

1. Context Building:
   - Loads project sources (with summaries)
   - Loads user and project memory
   - Builds dynamic system prompt

2. Claude API Call:
   - Sends conversation history + context
   - Provides tools: search_sources, store_memory

3. Tool Use Loop (Agentic Pattern):
   - Claude may call search_sources to query embeddings
   - Claude may call store_memory to save important info
   - Loop continues until Claude returns final text response

4. Response Handling:
   - Stores both user and assistant messages
   - Returns formatted response with citations

Routes:
- POST /projects/<id>/chats/<id>/messages - Send message, get AI response
"""
import json
from flask import jsonify, request, current_app, Response
from app.api.messages import messages_bp
from app.services.chat_services import main_chat_service


@messages_bp.route('/projects/<project_id>/chats/<chat_id>/messages', methods=['POST'])
def send_message(project_id, chat_id):
    """
    Send a message in a chat and get AI response.

    Educational Note: This endpoint is kept thin - all logic is delegated
    to main_chat_service. The service handles:
    1. Storing user message
    2. Building context with system prompt
    3. Calling Claude API
    4. Executing tool use loop
    5. Storing assistant response
    6. Syncing chat index

    Request Body:
        { "message": "Your question about the sources..." }

    Response:
        {
            "success": true,
            "user_message": { ... message object ... },
            "assistant_message": { ... message object with citations ... }
        }
    """
    try:
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400

        user_message_text = data['message']

        # Delegate all processing to main_chat_service
        # This is the RAG + agentic loop entry point
        user_msg, assistant_msg = main_chat_service.send_message(
            project_id=project_id,
            chat_id=chat_id,
            user_message_text=user_message_text
        )

        return jsonify({
            'success': True,
            'user_message': user_msg,
            'assistant_message': assistant_msg
        }), 200

    except ValueError as e:
        # Chat or project not found
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        current_app.logger.error(f"Error sending message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@messages_bp.route('/projects/<project_id>/chats/<chat_id>/messages/stream', methods=['POST'])
def send_message_stream(project_id, chat_id):
    """
    Stream a chat response via Server-Sent Events.

    Educational Note: Same logic as send_message but returns an SSE stream.
    Events: status (tool use updates), text_delta (streaming text), done, error.
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'Message is required'}), 400

    user_message_text = data['message']
    # Capture app and user identity before entering generator (runs outside request context)
    app = current_app._get_current_object()
    from app.services.auth.rbac import get_request_identity
    try:
        identity = get_request_identity()
        user_id = identity.user_id if identity else None
    except Exception:
        user_id = None

    def generate():
        with app.app_context():
            try:
                for event_type, event_data in main_chat_service.send_message_stream(
                    project_id=project_id,
                    chat_id=chat_id,
                    user_message_text=user_message_text,
                    user_id=user_id,
                ):
                    payload = {"type": event_type}
                    if event_type == "text_delta":
                        payload["content"] = event_data
                    elif event_type == "status":
                        payload["content"] = event_data
                    elif event_type == "done":
                        payload["user_message"] = event_data.get("user_message")
                        payload["assistant_message"] = event_data.get("assistant_message")
                    elif event_type == "error":
                        payload["content"] = event_data

                    yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:
                app.logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(
        generate(),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )
