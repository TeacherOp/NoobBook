"""
Database Upload - Handle database connections as sources.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import urlparse

from app.services.source_services import source_index_service
from app.services.data_services.database_service import database_service

logger = logging.getLogger(__name__)


def upload_database(project_id: str, name: str, connection_string: str) -> Dict[str, Any]:
    """
    Add a database connection as a source.
    
    Args:
        project_id: Project UUID
        name: Display name for the database
        connection_string: Database connection string
        
    Returns:
        Source creation result
    """
    try:
        # Validate connection
        db_type = database_service._detect_database_type(connection_string)
        validation = database_service._validate_database_support(db_type)
        if not validation["success"]:
            return validation
        
        # Test connection
        test_result = database_service._test_connection(connection_string, db_type)
        if not test_result["success"]:
            return test_result
        
        # Parse connection for metadata
        parsed = urlparse(connection_string)
        
        # Create source entry
        source_data = {
            "name": name,
            "type": "database",
            "status": "processing",
            "metadata": {
                "db_type": db_type,
                "host": parsed.hostname,
                "database": parsed.path.lstrip('/'),
                "connection_string": connection_string  # Store securely in real implementation
            }
        }
        
        # Add to source index
        result = source_index_service.add_source(project_id, source_data)
        if not result["success"]:
            return result
        
        source_id = result["source"]["id"]
        
        # Process database schema
        schema_result = _process_database_schema(project_id, source_id, connection_string, db_type)
        if schema_result["success"]:
            # Update status to completed
            source_index_service.update_source_status(project_id, source_id, "completed")
        else:
            # Update status to failed
            source_index_service.update_source_status(project_id, source_id, "failed")
            return schema_result
        
        return {
            "success": True,
            "source": result["source"],
            "message": f"Database '{name}' added successfully"
        }
        
    except Exception as e:
        logger.error(f"Error uploading database source: {e}")
        return {"success": False, "error": str(e)}


def _process_database_schema(project_id: str, source_id: str, connection_string: str, db_type: str) -> Dict[str, Any]:
    """
    Process database schema for RAG integration.
    
    Args:
        project_id: Project UUID
        source_id: Source UUID
        connection_string: Database connection string
        db_type: Database type (postgresql/mysql)
        
    Returns:
        Processing result
    """
    try:
        # Get schema information
        schema_result = database_service._get_schema_direct(connection_string, db_type)
        if not schema_result["success"]:
            return schema_result
        
        schema_info = schema_result["schema"]
        
        # Create processed content (schema summary for RAG)
        schema_text = _format_schema_for_rag(schema_info, db_type)
        
        # Save processed schema
        from app.utils.path_utils import get_processed_dir
        processed_dir = get_processed_dir(project_id)
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        schema_file = processed_dir / f"{source_id}_schema.txt"
        with open(schema_file, 'w') as f:
            f.write(schema_text)
        
        # Create chunks for RAG (each table as a chunk)
        chunks = _create_schema_chunks(schema_info, source_id)
        
        # Save chunks
        from app.utils.path_utils import get_chunks_dir
        chunks_dir = get_chunks_dir(project_id) / source_id
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        for i, chunk in enumerate(chunks):
            chunk_file = chunks_dir / f"chunk_{i}.txt"
            with open(chunk_file, 'w') as f:
                f.write(chunk)
        
        return {"success": True, "chunks_created": len(chunks)}
        
    except Exception as e:
        logger.error(f"Error processing database schema: {e}")
        return {"success": False, "error": str(e)}


def _format_schema_for_rag(schema_info: Dict[str, Any], db_type: str) -> str:
    """Format database schema for RAG processing."""
    lines = [f"Database Schema ({db_type.upper()})", "=" * 50, ""]
    
    for table in schema_info.get("tables", []):
        lines.append(f"Table: {table['name']}")
        lines.append("-" * (len(table['name']) + 7))
        
        for col in table["columns"]:
            nullable = " (nullable)" if col.get("nullable", True) else " (not null)"
            lines.append(f"  {col['name']}: {col['type']}{nullable}")
        
        lines.append("")
    
    return "\n".join(lines)


def _create_schema_chunks(schema_info: Dict[str, Any], source_id: str) -> List[str]:
    """Create chunks from database schema for RAG."""
    chunks = []
    
    for table in schema_info.get("tables", []):
        chunk_lines = [
            f"Table: {table['name']}",
            f"Source: Database ({source_id})",
            "",
            "Columns:"
        ]
        
        for col in table["columns"]:
            nullable = " (nullable)" if col.get("nullable", True) else " (not null)"
            chunk_lines.append(f"- {col['name']}: {col['type']}{nullable}")
        
        chunks.append("\n".join(chunk_lines))
    
    return chunks
