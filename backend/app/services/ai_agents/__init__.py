"""
AI Agents - Complex AI agents with agentic loops.

Educational Note: This folder contains AI agents that use tool loops
and multiple API calls to complete complex tasks. Unlike ai_services
(single API call), these agents iterate until a termination condition.

Agents:
- web_agent_service: Extracts content from URLs using web tools
  - Uses agentic loop with MAX_ITERATIONS limit
  - Tools: web_fetch, web_search, tavily_search, return_search_result
  - Saves execution logs for debugging

- email_agent_service: Generates HTML email templates
  - Uses agentic loop with MAX_ITERATIONS limit (15)
  - Tools: plan_email_template, generate_email_image, write_email_code
  - Orchestrates planning → image generation → HTML code writing

- website_agent_service: Generates complete websites (HTML/CSS/JS)
  - Uses agentic loop with MAX_ITERATIONS limit (30)
  - Tools: plan_website, generate_website_image, read_file, create_file,
    update_file_lines, insert_code, finalize_website
  - Orchestrates planning → image generation → iterative file creation/editing

- presentation_agent_service: Generates PowerPoint presentations
  - Uses agentic loop with MAX_ITERATIONS limit (40)
  - Tools: plan_presentation, create_base_styles, create_slide, finalize_presentation
  - Orchestrates planning → styling → slide creation → PPTX export
  - Export pipeline: HTML slides → Playwright screenshots → python-pptx

- blog_agent_service: Generates comprehensive blog posts
  - Uses agentic loop with MAX_ITERATIONS limit (20)
  - Tools: plan_blog_post, generate_blog_image, write_blog_post
  - Orchestrates planning → image generation → markdown writing
  - SEO-optimized content targeting specific keywords

- business_report_agent_service: Generates data-driven business reports
  - Uses agentic loop with MAX_ITERATIONS limit (25)
  - Tools: plan_business_report, analyze_csv_data, search_source_content, write_business_report
  - Multi-agent orchestration: calls csv_analyzer_agent for data analysis and charts
  - Combines quantitative data analysis with qualitative context

Key patterns:
- Agent loop with iteration limit
- Tool executor for routing tool calls
- Termination tool to signal completion
- Execution logging for debugging
"""

from app.services.ai_agents.web_agent_service import web_agent_service
from app.services.ai_agents.email_agent_service import email_agent_service
from app.services.ai_agents.website_agent_service import website_agent_service
from app.services.ai_agents.presentation_agent_service import presentation_agent_service
from app.services.ai_agents.blog_agent_service import blog_agent_service
from app.services.ai_agents.business_report_agent_service import (
    business_report_agent_service,
)
from app.services.ai_agents.wireframe_agent_service import wireframe_agent_service

__all__ = [
    "web_agent_service",
    "email_agent_service",
    "website_agent_service",
    "presentation_agent_service",
    "blog_agent_service",
    "business_report_agent_service",
    "wireframe_agent_service",
]
