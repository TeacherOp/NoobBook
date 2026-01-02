"""
Database Query Agent - AI agent for generating and executing SQL queries.

Educational Note: This agent analyzes user questions and generates appropriate
SQL queries to answer them using the connected databases.
"""
import logging
from typing import Dict, Any, List, Optional

from app.services.integrations.claude import claude_service
from app.services.data_services.database_service import database_service

logger = logging.getLogger(__name__)


class DatabaseQueryAgent:
    """
    AI agent that converts natural language questions into SQL queries
    and executes them on connected databases.
    """

    def __init__(self):
        self.system_prompt = """You are a SQL query assistant. Your job is to:

1. Analyze the user's question
2. Generate appropriate SQL SELECT queries
3. Return only the SQL query, no explanations

Rules:
- Only generate SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
- Use proper SQL syntax for PostgreSQL
- Be precise with column names and table names
- If the question is unclear, ask for clarification
- If no relevant tables exist, say "No relevant tables found"

Available schema information will be provided in the context."""

    def generate_query(self, question: str, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: User's natural language question
            schema_info: Database schema information
            
        Returns:
            Generated query or error
        """
        try:
            # Prepare context with schema
            schema_context = "Available database schema:\n\n"
            for table in schema_info.get("tables", []):
                schema_context += f"Table: {table['name']}\n"
                for col in table["columns"]:
                    schema_context += f"  - {col['name']} ({col['type']})\n"
                schema_context += "\n"

            # Generate query using Claude
            messages = [
                {"role": "user", "content": f"{schema_context}\nQuestion: {question}\n\nGenerate a SQL query to answer this question:"}
            ]

            response = claude_service.send_message(
                messages=messages,
                system_prompt=self.system_prompt,
                max_tokens=500,
                project_id="database_query"  # Add project_id for cost tracking
            )

            # Extract SQL query from response
            if isinstance(response, dict) and 'content' in response:
                query = response['content'][0]['text'].strip() if response['content'] else ""
            else:
                query = str(response).strip()
            
            # Basic validation
            if not query.lower().startswith('select'):
                return {"success": False, "error": "Generated query is not a SELECT statement"}
            
            return {"success": True, "query": query}
            
        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            return {"success": False, "error": str(e)}

    def answer_question(self, question: str, connection_id: str, user_id: str) -> Dict[str, Any]:
        """
        Answer a natural language question using database queries.
        
        Args:
            question: User's question
            connection_id: Database connection to use
            user_id: User ID for permissions
            
        Returns:
            Answer with query results
        """
        try:
            # Get schema information
            schema_result = database_service.get_schema_info(connection_id, user_id)
            if not schema_result["success"]:
                return schema_result

            schema_info = schema_result["schema"]
            
            # Generate SQL query
            query_result = self.generate_query(question, schema_info)
            if not query_result["success"]:
                return query_result

            sql_query = query_result["query"]
            
            # Execute query
            execution_result = database_service.execute_query(connection_id, sql_query, user_id)
            if not execution_result["success"]:
                return execution_result

            # Format response
            return {
                "success": True,
                "answer": {
                    "question": question,
                    "sql_query": sql_query,
                    "results": execution_result,
                    "summary": self._format_results_summary(execution_result)
                }
            }
            
        except Exception as e:
            logger.error(f"Error answering database question: {e}")
            return {"success": False, "error": str(e)}

    def _format_results_summary(self, results: Dict[str, Any]) -> str:
        """Format query results into a readable summary."""
        if not results.get("rows"):
            return "No results found."
        
        row_count = results["row_count"]
        if row_count == 1:
            return f"Found 1 result."
        else:
            return f"Found {row_count} results."


# Global instance
database_query_agent = DatabaseQueryAgent()
