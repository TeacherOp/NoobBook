"""
Model Loader - Admin-configurable Claude model overrides per use case.

Educational Note: Every prompt config in `data/prompts/*.json` has a baked-in
model (Haiku, Sonnet, or Opus). This module lets an admin override those models
at runtime per category (chat, studio, query agents, source extraction) without
editing 30+ JSON files.

How it works:
1. MODEL_CATEGORIES maps each category to an env var (e.g. CHAT_MODEL_OVERRIDE)
2. PROMPT_TO_CATEGORY maps each prompt name (e.g. "default", "presentation_agent")
   to its category
3. prompt_loader consults this module when building a prompt config. If the
   category's env var is set to a valid model id, it swaps config["model"].
4. Empty / unset env var = "Default" (use whatever the prompt JSON declares)

Persisted in .env, mirroring the existing ANTHROPIC_TIER pattern.
"""
import os
from typing import Dict, Optional


# The three Claude models we expose in the admin selector.
# IDs must match what the Anthropic SDK accepts.
AVAILABLE_MODELS: Dict[str, Dict] = {
    "claude-haiku-4-5-20251001": {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "description": "Fastest and cheapest. Best for simple or high-volume tasks.",
        "pricing": {"input_per_mtok": 1.0, "output_per_mtok": 5.0},
    },
    "claude-sonnet-4-6": {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "description": "Balanced speed and quality. Default for most tasks.",
        "pricing": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
    },
    "claude-opus-4-7": {
        "id": "claude-opus-4-7",
        "name": "Claude Opus 4.7",
        "description": "Most capable. Best for complex reasoning and high-quality generation.",
        "pricing": {"input_per_mtok": 5.0, "output_per_mtok": 25.0},
    },
}


# Use-case categories exposed in admin settings. Each maps to an env var.
MODEL_CATEGORIES: Dict[str, Dict[str, str]] = {
    "chat": {
        "id": "chat",
        "label": "Chat",
        "description": "Main conversation, auto-naming, and memory updates.",
        "env_var": "CHAT_MODEL_OVERRIDE",
    },
    "studio": {
        "id": "studio",
        "label": "Studio",
        "description": "Audio, video, presentations, websites, emails, mind maps, quizzes, and other generation.",
        "env_var": "STUDIO_MODEL_OVERRIDE",
    },
    "query": {
        "id": "query",
        "label": "Query Agents",
        "description": "Database, CSV, and Freshdesk analysis agents.",
        "env_var": "QUERY_MODEL_OVERRIDE",
    },
    "extraction": {
        "id": "extraction",
        "label": "Source Extraction",
        "description": "Background processing: PDF, PPTX, image, CSV extraction and source summaries.",
        "env_var": "EXTRACTION_MODEL_OVERRIDE",
    },
}


# Maps prompt names (without the "_prompt" suffix) to their category.
# Prompts not listed here (web_agent, deep_research_agent) keep their JSON-baked
# model and are unaffected by admin overrides.
PROMPT_TO_CATEGORY: Dict[str, str] = {
    # Chat
    "default": "chat",
    "chat_naming": "chat",
    "memory": "chat",
    # Studio
    "audio_script": "studio",
    "video": "studio",
    "mind_map": "studio",
    "quiz": "studio",
    "flash_cards": "studio",
    "social_posts": "studio",
    "infographic": "studio",
    "flow_diagram": "studio",
    "ad_creative": "studio",
    "component_agent": "studio",
    "wireframe_agent": "studio",
    "wireframe": "studio",
    "website_agent": "studio",
    "presentation_agent": "studio",
    "email_agent": "studio",
    "blog_agent": "studio",
    "prd_agent": "studio",
    "business_report_agent": "studio",
    "marketing_strategy_agent": "studio",
    # Query agents
    "database_analyzer_agent": "query",
    "csv_analyzer_agent": "query",
    "freshdesk_analyzer_agent": "query",
    # Source extraction
    "pdf_extraction": "extraction",
    "pptx_extraction": "extraction",
    "image_extraction": "extraction",
    "csv_processor": "extraction",
    "summary": "extraction",
}


def get_category_override(category: str) -> Optional[str]:
    """
    Read the override model for a category from the environment.

    Returns the model id if the env var is set AND names a known model,
    otherwise None (meaning "no override, use the prompt's own model").
    """
    category_info = MODEL_CATEGORIES.get(category)
    if not category_info:
        return None
    value = os.environ.get(category_info["env_var"], "").strip()
    if value and value in AVAILABLE_MODELS:
        return value
    return None


def get_model_override_for_prompt(prompt_name: str) -> Optional[str]:
    """
    Given a prompt name (e.g. "default", "presentation_agent"), return the
    admin-configured override model for its category, or None if no override
    is set or the prompt is not categorized.
    """
    category = PROMPT_TO_CATEGORY.get(prompt_name)
    if not category:
        return None
    return get_category_override(category)


def get_current_settings() -> Dict[str, Optional[str]]:
    """
    Return the current override for every category.

    Used by the GET /settings/models endpoint. A value of None means
    "Default" (the prompt's own model is used).
    """
    return {cat_id: get_category_override(cat_id) for cat_id in MODEL_CATEGORIES}


def get_default_models_for_category(category: str) -> Dict[str, list]:
    """
    For a given category, return a map of {model_id: [prompt_names]} showing
    which model each prompt in the category uses by default (i.e. its
    JSON-baked model, ignoring any admin override).

    Used by the settings UI to clearly explain what "Default" means for each
    category — e.g., chat is mostly Sonnet but uses Haiku for chat_naming and
    memory; studio is mostly Sonnet with three Opus prompts.
    """
    # Lazy import to avoid circular dependency at module load time
    from app.config.prompt_loader import prompt_loader

    breakdown: Dict[str, list] = {}
    for prompt_name, cat in PROMPT_TO_CATEGORY.items():
        if cat != category:
            continue
        config = prompt_loader.get_prompt_config(prompt_name)
        if config is None:
            continue
        # Use raw_model() to bypass any active override and get the
        # JSON-baked model — that's what "Default" actually resolves to.
        model = config.raw_model() if hasattr(config, "raw_model") else config.get("model")
        if not model:
            continue
        breakdown.setdefault(model, []).append(prompt_name)
    # Sort prompt lists for stable output
    for prompts in breakdown.values():
        prompts.sort()
    return breakdown


def get_all_default_models() -> Dict[str, Dict[str, list]]:
    """
    Return {category_id: {model_id: [prompt_names]}} for every category.

    Used by GET /settings/models so the frontend can render the per-prompt
    default breakdown under each dropdown.
    """
    return {cat_id: get_default_models_for_category(cat_id) for cat_id in MODEL_CATEGORIES}
