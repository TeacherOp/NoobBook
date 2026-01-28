"""
Main entry point for NoobBook backend.

Educational Note: This file creates and runs the Flask application.
We keep it separate from the app factory to maintain clean separation
of concerns and make testing easier.
"""
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv


def clear_pycache():
    """
    Clear __pycache__ folders in the project code (excluding virtual environment).

    Educational Note: Python creates __pycache__ folders containing
    compiled bytecode (.pyc files). Clearing these on startup ensures
    fresh compilation and avoids stale cache issues during development.
    """
    backend_dir = Path(__file__).parent
    pycache_count = 0

    # Folders to skip (virtual environments, node_modules, etc.)
    skip_folders = {'myvenv', 'venv', '.venv', 'env', 'node_modules', '.git'}

    for pycache_dir in backend_dir.rglob("__pycache__"):
        # Skip if any parent folder is in skip_folders
        if any(part in skip_folders for part in pycache_dir.parts):
            continue
        try:
            shutil.rmtree(pycache_dir)
            pycache_count += 1
        except Exception as e:
            print(f"Warning: Could not delete {pycache_dir}: {e}")

    if pycache_count > 0:
        print(f"Cleared {pycache_count} __pycache__ folders")


# Clear pycache on startup
clear_pycache()

from app import create_app, socketio

# Load environment variables from .env file
load_dotenv()

# Get configuration name from environment or use default
config_name = os.getenv('FLASK_ENV', 'development')

# Create the Flask application
app = create_app(config_name)


if __name__ == '__main__':
    """
    Run the Flask application.

    Educational Note: We use socketio.run instead of app.run when
    using Flask-SocketIO for WebSocket support (real-time features).
    """
    port = int(os.getenv('PORT', 5001))
    debug = config_name == 'development'

    print(f"""
    ========================================
         NoobBook Backend Server
    ========================================
      Running on: http://localhost:{port}
      Environment: {config_name}
      Debug Mode: {debug}
    ========================================

    Press CTRL+C to stop the server
    """)

    # Run with SocketIO for WebSocket support
    socketio.run(
        app,
        host='0.0.0.0',  # Allow connections from any IP
        port=port,
        debug=debug,
        use_reloader=debug,  # Auto-reload on code changes in debug mode
        allow_unsafe_werkzeug=True  # Allow Werkzeug dev server (required for Flask-SocketIO)
    )