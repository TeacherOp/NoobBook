"""
Database Tool Executor - Executes database queries from chat tool calls.

Educational Note: This executor handles database tool calls from the chat system,
allowing users to query databases through natural language in chat.
"""
import logging
from .decorators import safe_tool_handler
from app.services.ai_agents.database_query_agent import database_query_agent

logger = logging.getLogger(__name__)

class DatabaseToolExecutor:
    """
    Executor for database-related tool calls in chat.
    """

    @safe_tool_handler("Database tool execution failed")
    def execute(self, tool_call, project_id, user_id="default_user"):
        tool_name = tool_call.get("name")
        tool_input = tool_call.get("input", {})

        if tool_name == "query_database":
            return self._query_database(tool_input, user_id)

        return {
            "success": False,
            "error": f"Unknown database tool: {tool_name}"
        }

    @safe_tool_handler("Database query tool failed")
    def _query_database(self, tool_input, user_id):
        question = tool_input.get("question")
        connection_id = tool_input.get("connection_id")

        if not question or not connection_id:
            return {
                "success": False,
                "error": "Question and connection_id are required"
            }

        result = database_query_agent.answer_question(question, connection_id, user_id)

        if result["success"]:
            answer = result["answer"]
            return {
                "success": True,
                "result": {
                    "question": answer["question"],
                    "sql_query": answer["sql_query"],
                    "row_count": answer["results"]["row_count"],
                    "summary": answer["summary"],
                    "data": answer["results"]["rows"][:10],
                },
            }
        
        return result
