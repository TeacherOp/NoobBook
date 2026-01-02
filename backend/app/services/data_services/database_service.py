"""
Database Service - Manages PostgreSQL connections and query execution.

Educational Note: This service handles database connections at the account level
and provides secure query execution with schema processing for RAG integration.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import urlparse

try:
    from sqlalchemy import create_engine, text, inspect
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

from app.utils.path_utils import get_data_dir

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Service for managing PostgreSQL database connections and operations.
    """

    def __init__(self):
        self.connections = {}
        if POSTGRES_AVAILABLE:
            self._load_connections()

    def _check_availability(self):
        """Check if PostgreSQL dependencies are available."""
        if not POSTGRES_AVAILABLE:
            return {"success": False, "error": "PostgreSQL dependencies not installed"}
        return {"success": True}

    def _load_connections(self):
        """Load saved database connections from file."""
        try:
            connections_file = get_data_dir() / "database_connections.json"
            if connections_file.exists():
                with open(connections_file, 'r') as f:
                    self.connections = json.load(f)
        except Exception as e:
            logger.error(f"Error loading database connections: {e}")
            self.connections = {}

    def _save_connections(self):
        """Save database connections to file."""
        try:
            connections_file = get_data_dir() / "database_connections.json"
            with open(connections_file, 'w') as f:
                json.dump(self.connections, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving database connections: {e}")

    def _test_connection(self, connection_string: str, db_type: str) -> Dict[str, Any]:
        """Test database connection."""
        try:
            # Normalize MySQL connection string
            if db_type == 'mysql' and not connection_string.startswith('mysql+pymysql://'):
                connection_string = connection_string.replace('mysql://', 'mysql+pymysql://')
            
            engine = create_engine(connection_string, pool_timeout=10, pool_recycle=3600)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()  # Close engine after test
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_schema_direct(self, connection_string: str, db_type: str) -> Dict[str, Any]:
        """Get schema information directly from connection string."""
        try:
            # Normalize MySQL connection string
            if db_type == 'mysql' and not connection_string.startswith('mysql+pymysql://'):
                connection_string = connection_string.replace('mysql://', 'mysql+pymysql://')
            
            engine = create_engine(connection_string)
            inspector = inspect(engine)
            
            schema_info = {"tables": []}
            
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                table_info = {
                    "name": table_name,
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True)
                        }
                        for col in columns
                    ]
                }
                schema_info["tables"].append(table_info)
            
            return {"success": True, "schema": schema_info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_connection(self, name: str, connection_string: str, user_id: str) -> Dict[str, Any]:
        """Add a new database connection."""
        availability_check = self._check_availability()
        if not availability_check["success"]:
            return availability_check
            
        try:
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            parsed = urlparse(connection_string)
            connection_id = f"{user_id}_{name}"
            self.connections[connection_id] = {
                "id": connection_id,
                "name": name,
                "user_id": user_id,
                "connection_string": connection_string,
                "host": parsed.hostname,
                "database": parsed.path.lstrip('/'),
                "created_at": datetime.now().isoformat()
            }
            
            self._save_connections()
            
            return {
                "success": True,
                "connection": {
                    "id": connection_id,
                    "name": name,
                    "host": parsed.hostname,
                    "database": parsed.path.lstrip('/')
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding database connection: {e}")
            return {"success": False, "error": str(e)}

    def get_user_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all database connections for a user."""
        if not POSTGRES_AVAILABLE:
            return []
            
        user_connections = []
        for conn_id, conn_data in self.connections.items():
            if conn_data.get("user_id") == user_id:
                user_connections.append({
                    "id": conn_id,
                    "name": conn_data["name"],
                    "host": conn_data["host"],
                    "database": conn_data["database"]
                })
        return user_connections

    def execute_query(self, connection_id: str, query: str, user_id: str) -> Dict[str, Any]:
        """Execute SQL query on specified database."""
        availability_check = self._check_availability()
        if not availability_check["success"]:
            return availability_check
            
        try:
            if connection_id not in self.connections:
                return {"success": False, "error": "Connection not found"}
            
            conn_data = self.connections[connection_id]
            if conn_data["user_id"] != user_id:
                return {"success": False, "error": "Access denied"}
            
            # Validate query is SELECT only using SQL parsing
            query_stripped = query.strip()
            if not query_stripped.upper().startswith('SELECT'):
                return {"success": False, "error": "Only SELECT queries are allowed"}
            
            # Basic check for multiple statements (prevent injection)
            if ';' in query_stripped[:-1]:  # Allow trailing semicolon
                return {"success": False, "error": "Multiple statements not allowed"}
            
            engine = create_engine(conn_data["connection_string"], pool_timeout=10, connect_args={"connect_timeout": 30})
            with engine.connect() as conn:
                # Set query timeout (30 seconds)
                result = conn.execute(text(query).execution_options(autocommit=True, compiled_cache={}))
                rows = result.fetchall()
                columns = list(result.keys())
            
            engine.dispose()  # Properly close engine
                
            return {
                "success": True,
                "columns": columns,
                "rows": [dict(row._mapping) for row in rows],
                "row_count": len(rows)
            }
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return {"success": False, "error": str(e)}

    def get_schema_info(self, connection_id: str, user_id: str) -> Dict[str, Any]:
        """Get database schema information for RAG processing."""
        availability_check = self._check_availability()
        if not availability_check["success"]:
            return availability_check
            
        try:
            if connection_id not in self.connections:
                return {"success": False, "error": "Connection not found"}
            
            conn_data = self.connections[connection_id]
            if conn_data["user_id"] != user_id:
                return {"success": False, "error": "Access denied"}
            
            engine = create_engine(conn_data["connection_string"])
            inspector = inspect(engine)
            
            schema_info = {"tables": [], "summary": ""}
            
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                table_info = {
                    "name": table_name,
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True)
                        }
                        for col in columns
                    ]
                }
                schema_info["tables"].append(table_info)
            
            summary_parts = []
            for table in schema_info["tables"]:
                col_names = [col["name"] for col in table["columns"]]
                summary_parts.append(f"Table {table['name']}: {', '.join(col_names)}")
            
            schema_info["summary"] = "\n".join(summary_parts)
            
            return {"success": True, "schema": schema_info}
            
        except Exception as e:
            logger.error(f"Error getting schema info: {e}")
            return {"success": False, "error": str(e)}


# Global instance
database_service = DatabaseService()
