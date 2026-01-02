"""
Tool Executors - Handle tool call execution for AI services.

Educational Note: This folder contains executors that handle tool calls
from Claude during chat or agent loops. Each executor is responsible for:
- Receiving tool call parameters
- Executing the appropriate action
- Returning results back to the AI

Executors:
- memory_executor: Handles store_memory tool calls (non-blocking, background task)
- source_search_executor: Handles search_sources tool calls (full content or semantic search)
- web_agent_executor: Routes tool calls for web agent (tavily_search, return_search_result)
- deep_research_executor: Routes tool calls for deep research (write_research_to_file, tavily_search_advance)
- csv_analyzer_agent_executor: Handles CSV analysis agent tool calls (module with execute function)
- studio_signal_executor: Handles studio_signal tool calls (non-blocking, background task)
- studio_audio_executor: Handles audio overview tools (read_source_content, write_script_section)
- email_agent_executor: Handles email template generation (background task)
- website_agent_executor: Handles website generation (background task)
- presentation_agent_executor: Handles presentation generation (background task)
"""
from app.services.tool_executors.memory_executor import memory_executor
from app.services.tool_executors.source_search_executor import source_search_executor
from app.services.tool_executors.web_agent_executor import web_agent_executor
from app.services.tool_executors.deep_research_executor import deep_research_executor
from app.services.tool_executors import csv_analyzer_agent_executor  # Module import (has execute function)
from app.services.tool_executors.studio_signal_executor import studio_signal_executor
from app.services.tool_executors.studio_audio_executor import studio_audio_executor
from app.services.tool_executors.email_agent_executor import email_agent_executor
from app.services.tool_executors.website_agent_executor import website_agent_executor
from app.services.tool_executors.presentation_agent_executor import presentation_agent_executor
from app.services.tool_executors.database_tool_executor import execute_database_tool

__all__ = [
    "memory_executor",
    "source_search_executor",
    "web_agent_executor",
    "deep_research_executor",
    "csv_analyzer_agent_executor",
    "studio_signal_executor",
    "studio_audio_executor",
    "email_agent_executor",
    "website_agent_executor",
    "presentation_agent_executor",
    "execute_database_tool"
]
