"""
Static map of prompt name → service file paths that consume it.

Surfaced in the admin Prompts editor so an operator editing
``memory_prompt`` can see at a glance "this affects
``memory_service.merge_memory()``" instead of guessing.

Maintained by hand — when a new prompt is added or moved, update this map.
The list is informational; an empty array just hides the breadcrumb in the
UI, nothing else breaks.

Tip when editing: ``grep -r "get_prompt_config(\"<prompt_name>\")"
backend/app/services/`` will show every caller.
"""
from __future__ import annotations

from typing import Dict, List


PROMPT_REFERENCED_BY: Dict[str, List[str]] = {
    # Chat
    "default": ["app/services/chat_services/main_chat_service.py"],
    "chat_naming": ["app/services/data_services/chat_naming_service.py"],
    "memory": ["app/services/data_services/memory_service.py"],

    # Source extraction
    "pdf_extraction": ["app/services/ai_services/pdf_service.py"],
    "pptx_extraction": ["app/services/ai_services/pptx_service.py"],
    "image_extraction": ["app/services/ai_services/image_service.py"],
    "csv_processor": ["app/services/source_services/source_processing/csv_processor.py"],
    "summary": ["app/services/data_services/summary_service.py"],

    # Studio — content generation
    "ad_creative": ["app/services/studio_services/ad_creative_service.py"],
    "audio_script": ["app/services/studio_services/audio_overview_service.py"],
    "blog_agent": ["app/services/studio_services/blog_service.py"],
    "business_report_agent": ["app/services/studio_services/business_report_service.py"],
    "component_agent": ["app/services/studio_services/component_service.py"],
    "email_agent": ["app/services/studio_services/email_service.py"],
    "flash_cards": ["app/services/studio_services/flash_cards_service.py"],
    "flow_diagram": ["app/services/studio_services/flow_diagram_service.py"],
    "infographic": ["app/services/studio_services/infographic_service.py"],
    "marketing_strategy_agent": ["app/services/studio_services/marketing_strategy_service.py"],
    "mind_map": ["app/services/studio_services/mind_map_service.py"],
    "prd_agent": ["app/services/studio_services/prd_service.py"],
    "presentation_agent": ["app/services/studio_services/presentation_service.py"],
    "quiz": ["app/services/studio_services/quiz_service.py"],
    "social_posts": ["app/services/studio_services/social_posts_service.py"],
    "video": ["app/services/studio_services/video_service.py"],
    "website_agent": ["app/services/studio_services/website_service.py"],
    "wireframe": ["app/services/studio_services/wireframe_service.py"],
    "wireframe_agent": ["app/services/studio_services/wireframe_service.py"],

    # Query / data agents
    "csv_analyzer_agent": ["app/services/ai_agents/csv_analyzer_agent.py"],
    "database_analyzer_agent": ["app/services/ai_agents/database_analyzer_agent.py"],
    "freshdesk_analyzer_agent": ["app/services/ai_agents/freshdesk_analyzer_agent.py"],
    "mixpanel_analyzer_agent": ["app/services/ai_agents/mixpanel_analyzer_agent.py"],
    "deep_research_agent": ["app/services/ai_agents/deep_research_agent.py"],
    "web_agent": ["app/services/ai_agents/web_agent_service.py"],
}


def referenced_by(prompt_name: str) -> List[str]:
    """Return the list of file paths that consume this prompt, or []."""
    return list(PROMPT_REFERENCED_BY.get(prompt_name, []))
