"""
Health check endpoint for Docker containers
"""
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "noobbook-backend",
        "version": "1.0.0"
    }), 200
