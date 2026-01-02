"""
Database Tool Executor - Execute database queries from chat.
"""
import logging
from typing import Dict, Any

from app.services.ai_agents.database_query_agent import database_query_agent

logger = logging.getLogger(__name__)


def execute_database_tool(tool_call: Dict[str, Any], project_id: str, user_id: str = "default_user") -> Dict[str, Any]:
    """
    Execute database query tool from chat.
    
    Args:
        tool_call: Tool call with connection_id and question
        project_id: Project ID for context
        
    Returns:
        Query results
    """
    try:
        connection_id = tool_call.get("connection_id")
        question = tool_call.get("question")
        
        if not connection_id or not question:
            return {"error": "connection_id and question are required"}
        
        # Use provided user_id for proper access control
        result = database_query_agent.answer_question(question, connection_id, user_id, project_id)
        
        if result["success"]:
            return {
                "success": True,
                "sql_query": result["answer"]["sql_query"],
                "results": result["answer"]["results"],
                "summary": result["answer"]["summary"]
            }
        else:
            return {"error": result["error"]}
            
    except Exception as e:
        logger.error(f"Error executing database tool: {e}")
        return {"error": str(e)}
