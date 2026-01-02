"""
Database API Routes - REST endpoints for database connection management.

Educational Note: These routes handle database connection CRUD operations
and query execution through the chat system.
"""
from flask import Blueprint, request, jsonify
import logging

from app.services.data_services.database_service import database_service
from app.services.ai_agents.database_query_agent import database_query_agent

logger = logging.getLogger(__name__)

database_bp = Blueprint('database', __name__)


@database_bp.route('/connections', methods=['POST'])
def add_database_connection():
    """Add a new database connection."""
    try:
        data = request.get_json()
        name = data.get('name')
        connection_string = data.get('connection_string')
        user_id = data.get('user_id', 'default_user')  # TODO: Get from auth
        
        if not name or not connection_string:
            return jsonify({"error": "Name and connection_string are required"}), 400
        
        result = database_service.add_connection(name, connection_string, user_id)
        
        if result["success"]:
            return jsonify(result["connection"]), 201
        else:
            return jsonify({"error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error in add_database_connection: {e}")
        return jsonify({"error": "Internal server error"}), 500


@database_bp.route('/connections', methods=['GET'])
def get_database_connections():
    """Get all database connections for the user."""
    try:
        user_id = request.args.get('user_id', 'default_user')  # TODO: Get from auth
        
        connections = database_service.get_user_connections(user_id)
        return jsonify({"connections": connections}), 200
        
    except Exception as e:
        logger.error(f"Error in get_database_connections: {e}")
        return jsonify({"error": "Internal server error"}), 500


@database_bp.route('/connections/<connection_id>/query', methods=['POST'])
def execute_database_query():
    """Execute a SQL query on a database connection."""
    try:
        connection_id = request.view_args['connection_id']
        data = request.get_json()
        query = data.get('query')
        user_id = data.get('user_id', 'default_user')  # TODO: Get from auth
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        result = database_service.execute_query(connection_id, query, user_id)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify({"error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error in execute_database_query: {e}")
        return jsonify({"error": "Internal server error"}), 500


@database_bp.route('/connections/<connection_id>/schema', methods=['GET'])
def get_database_schema():
    """Get schema information for a database connection."""
    try:
        connection_id = request.view_args['connection_id']
        user_id = request.args.get('user_id', 'default_user')  # TODO: Get from auth
        
        result = database_service.get_schema_info(connection_id, user_id)
        
        if result["success"]:
            return jsonify(result["schema"]), 200
        else:
            return jsonify({"error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error in get_database_schema: {e}")
        return jsonify({"error": "Internal server error"}), 500


@database_bp.route('/connections/<connection_id>/ask', methods=['POST'])
def ask_database_question():
    """Ask a natural language question about the database."""
    try:
        connection_id = request.view_args['connection_id']
        data = request.get_json()
        question = data.get('question')
        user_id = data.get('user_id', 'default_user')  # TODO: Get from auth
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        result = database_query_agent.answer_question(question, connection_id, user_id)
        
        if result["success"]:
            return jsonify(result["answer"]), 200
        else:
            return jsonify({"error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error in ask_database_question: {e}")
        return jsonify({"error": "Internal server error"}), 500
