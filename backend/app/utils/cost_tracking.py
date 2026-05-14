"""
Cost Tracking Utility - Track and calculate API costs per project.

Educational Note: This utility tracks Claude API usage costs by model.
Costs are stored in Supabase projects table and updated after each API call.

Pricing (per 1M tokens):
- Opus:   $5 input, $25 output
- Sonnet: $3 input, $15 output
- Haiku:  $1 input, $5 output

Prompt-cache multipliers (Anthropic):
- cache_creation_input_tokens: 1.25× the input rate (one-time write cost)
- cache_read_input_tokens:     0.10× the input rate (per cached read)
"""
import logging
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


# Pricing per 1M tokens
PRICING = {
    "opus": {"input": 5.0, "output": 25.0},
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 1.0, "output": 5.0},
}

# Prompt-cache multipliers applied to the per-model input rate.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

# Tracked model buckets, in stable order. Used by _get_default_costs and
# _ensure_cost_structure so the breakdown always shows every model bucket
# even if a project has only used some of them.
_MODEL_KEYS = ("opus", "sonnet", "haiku")

# Lock for thread-safe operations
_lock = Lock()


def _get_model_key(model_string: str) -> str:
    """
    Extract model key (opus/sonnet/haiku) from full model string.

    Args:
        model_string: Full model ID like "claude-sonnet-4-6"

    Returns:
        "opus", "sonnet", or "haiku"
    """
    model_lower = model_string.lower()
    if "opus" in model_lower:
        return "opus"
    if "sonnet" in model_lower:
        return "sonnet"
    if "haiku" in model_lower:
        return "haiku"
    # Default to sonnet pricing for unknown models
    return "sonnet"


def _calculate_cost(
    model_key: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """
    Calculate cost for a single API call, including any prompt-cache usage.

    Args:
        model_key: "opus", "sonnet", or "haiku"
        input_tokens: Non-cached input tokens (billed at the model's input rate)
        output_tokens: Output tokens (billed at the model's output rate)
        cache_creation_tokens: Tokens written to the prompt cache. Billed at
            1.25× the input rate (one-time, amortized over reads).
        cache_read_tokens: Tokens served from the prompt cache. Billed at
            0.1× the input rate.

    Returns:
        Total cost in USD for this single call.
    """
    pricing = PRICING.get(model_key, PRICING["sonnet"])
    input_rate = pricing["input"]
    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    cache_write_cost = (cache_creation_tokens / 1_000_000) * input_rate * CACHE_WRITE_MULTIPLIER
    cache_read_cost = (cache_read_tokens / 1_000_000) * input_rate * CACHE_READ_MULTIPLIER
    return input_cost + output_cost + cache_write_cost + cache_read_cost


def _calculate_cache_savings(
    model_key: str,
    cache_creation_tokens: int,
    cache_read_tokens: int,
) -> float:
    """
    Compute the net dollar savings produced by prompt caching for this call.

    Compares the actual cache-aware cost against the counterfactual where the
    same tokens would have been billed at the full input rate. Result can be
    negative on the first call (only writes, no reads yet) — that's correct;
    the dashboard should reflect the true net.
    """
    pricing = PRICING.get(model_key, PRICING["sonnet"])
    input_rate = pricing["input"]
    read_gain = (cache_read_tokens / 1_000_000) * input_rate * (1.0 - CACHE_READ_MULTIPLIER)
    write_premium = (cache_creation_tokens / 1_000_000) * input_rate * (CACHE_WRITE_MULTIPLIER - 1.0)
    return read_gain - write_premium


def _get_project_service():
    """Get project service (lazy import to avoid circular imports)."""
    from app.services.data_services import project_service
    return project_service


def _get_chat_service():
    """Get chat service (lazy import to avoid circular imports)."""
    from app.services.data_services import chat_service
    return chat_service


def _load_costs(project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load cost tracking data from Supabase."""
    try:
        project_service = _get_project_service()
        owner_id = user_id or project_service.get_project_owner_id(project_id)
        if not owner_id:
            return None
        return project_service.get_project_costs(project_id, user_id=owner_id)
    except Exception as e:
        logger.error("Error loading costs for %s: %s", project_id, e)
        return None


def _save_costs(project_id: str, costs: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """Save cost tracking data to Supabase."""
    try:
        project_service = _get_project_service()
        owner_id = user_id or project_service.get_project_owner_id(project_id)
        if not owner_id:
            return False
        return project_service.update_project_costs(project_id, costs, user_id=owner_id)
    except Exception as e:
        logger.error("Error saving costs for %s: %s", project_id, e)
        return False


def _load_chat_costs(chat_id: str) -> Optional[Dict[str, Any]]:
    """Load cost tracking data for a chat from Supabase."""
    try:
        chat_service = _get_chat_service()
        return chat_service.get_chat_costs_raw(chat_id)
    except Exception as e:
        logger.error("Error loading chat costs for %s: %s", chat_id, e)
        return None


def _save_chat_costs(chat_id: str, costs: Dict[str, Any]) -> str:
    """Save cost tracking data for a chat to Supabase.

    Returns one of ``"ok"``, ``"missing"``, ``"error"`` — see
    ``chat_service.update_chat_costs`` for semantics. ``"missing"``
    means the chat row no longer exists (e.g. user deleted the chat
    while the stream was still running); the caller should treat this
    as expected operational state, not a failure.
    """
    try:
        chat_service = _get_chat_service()
        return chat_service.update_chat_costs(chat_id, costs)
    except Exception as e:
        logger.error("Error saving chat costs for %s: %s", chat_id, e)
        return "error"


def _empty_bucket() -> Dict[str, Any]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0.0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }


def _get_default_costs() -> Dict[str, Any]:
    """
    Get default cost tracking structure.

    Educational Note: Returns the initial cost tracking structure
    for projects that don't have costs yet.
    """
    return {
        "total_cost": 0.0,
        "cache_savings": 0.0,
        "by_model": {key: _empty_bucket() for key in _MODEL_KEYS},
    }


def _ensure_cost_structure(costs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure costs dict has proper structure.

    Educational Note: Initializes the cost tracking structure if it
    doesn't exist, preserving any existing data.
    """
    if costs is None:
        return _get_default_costs()

    # Ensure all required fields exist
    if "total_cost" not in costs:
        costs["total_cost"] = 0.0
    if "cache_savings" not in costs:
        costs["cache_savings"] = 0.0
    if "by_model" not in costs:
        costs["by_model"] = {}
    if "images" not in costs:
        costs["images"] = {}

    for model in _MODEL_KEYS:
        bucket = costs["by_model"].get(model)
        if bucket is None:
            costs["by_model"][model] = _empty_bucket()
            continue
        # Backfill cache fields for projects created before cache tracking.
        bucket.setdefault("cache_creation_tokens", 0)
        bucket.setdefault("cache_read_tokens", 0)

    return costs


def _apply_usage(
    costs: Dict[str, Any],
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Dict[str, Any]:
    """
    Mutate a costs dict in place: add this call's tokens + cost to the
    correct model bucket and bump the total. Returns the same dict.

    Extracted so both project-level and chat-level updates share identical math.
    """
    model_key = _get_model_key(model)
    call_cost = _calculate_cost(
        model_key,
        input_tokens,
        output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
    )

    bucket = costs["by_model"][model_key]
    bucket["input_tokens"] += input_tokens
    bucket["output_tokens"] += output_tokens
    bucket["cost"] += call_cost
    bucket["cache_creation_tokens"] = bucket.get("cache_creation_tokens", 0) + cache_creation_tokens
    bucket["cache_read_tokens"] = bucket.get("cache_read_tokens", 0) + cache_read_tokens

    costs["total_cost"] += call_cost
    costs["cache_savings"] = costs.get("cache_savings", 0.0) + _calculate_cache_savings(
        model_key, cache_creation_tokens, cache_read_tokens
    )
    return costs


def add_usage(
    project_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    Add API usage to project (and optionally chat) cost tracking.

    Educational Note: This function is called after each Claude API call
    to update the cumulative cost tracking in Supabase. When chat_id is
    provided, the same usage is also added to chats.costs so per-chat
    spend can be shown in the chat header. Both updates happen inside a
    single lock so project and chat totals never drift.

    Args:
        project_id: The project UUID
        model: Full model string (e.g., "claude-sonnet-4-6")
        input_tokens: Number of non-cached input tokens used
        output_tokens: Number of output tokens used
        user_id: Optional owner id (falls back to project lookup)
        chat_id: Optional chat UUID — when set, chat-level costs update too
        cache_creation_tokens: Anthropic `cache_creation_input_tokens`
            (billed at 1.25× the input rate).
        cache_read_tokens: Anthropic `cache_read_input_tokens`
            (billed at 0.1× the input rate).

    Returns:
        Updated project cost tracking data or None if project save failed
    """
    with _lock:
        # --- Project-level update (unchanged behavior) ---
        project_costs = _load_costs(project_id, user_id=user_id)
        if project_costs is None:
            project_costs = _get_default_costs()
        project_costs = _ensure_cost_structure(project_costs)
        _apply_usage(
            project_costs,
            model,
            input_tokens,
            output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
        )

        if not _save_costs(project_id, project_costs, user_id=user_id):
            logger.warning("Failed to save costs for project %s", project_id)
            project_costs = None

        # --- Chat-level update (only when chat_id provided) ---
        if chat_id:
            chat_costs = _load_chat_costs(chat_id)
            if chat_costs is None:
                chat_costs = _get_default_costs()
            chat_costs = _ensure_cost_structure(chat_costs)
            _apply_usage(
                chat_costs,
                model,
                input_tokens,
                output_tokens,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
            )

            save_status = _save_chat_costs(chat_id, chat_costs)
            if save_status == "missing":
                # Chat row gone (typically: user deleted the chat while
                # the stream was still producing tokens). Expected
                # operational state — log at INFO so it doesn't read as
                # a real failure in the logs.
                logger.info(
                    "Skipping chat cost save for %s — chat row not found (likely deleted mid-stream)",
                    chat_id,
                )
            elif save_status == "error":
                logger.warning("Failed to save costs for chat %s", chat_id)

        # --- User period spend tracking (for per-user spending limits) ---
        resolved_user_id = user_id
        if not resolved_user_id:
            try:
                ps = _get_project_service()
                resolved_user_id = ps.get_project_owner_id(project_id)
            except Exception:
                pass
        if resolved_user_id:
            model_key = _get_model_key(model)
            call_cost = _calculate_cost(
                model_key,
                input_tokens,
                output_tokens,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
            )
            record_user_period_spend(resolved_user_id, call_cost)

        return project_costs


def add_image_usage(
    project_id: str,
    model: str,
    size: str,
    quality: str,
    n: int,
    unit_cost: float,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Add image generation usage to project cost tracking.

    Image-gen costs are kept in a separate `images` bucket from Claude's
    `by_model` so the Claude breakdown stays clean. The bucket shape is:

        costs["images"][model] = {
            "count": int,
            "cost": float,
            "by_size_quality": {
                f"{size}-{quality}": {"count": int, "cost": float}
            }
        }

    The top-level `total_cost` rolls up everything (Claude + images).
    """
    call_cost = unit_cost * n
    bucket_key = f"{size}-{quality}"

    with _lock:
        project_costs = _load_costs(project_id, user_id=user_id)
        if project_costs is None:
            project_costs = _get_default_costs()
        project_costs = _ensure_cost_structure(project_costs)

        images = project_costs.setdefault("images", {})
        bucket = images.setdefault(model, {"count": 0, "cost": 0.0, "by_size_quality": {}})
        bucket["count"] += n
        bucket["cost"] += call_cost

        sq_bucket = bucket["by_size_quality"].setdefault(bucket_key, {"count": 0, "cost": 0.0})
        sq_bucket["count"] += n
        sq_bucket["cost"] += call_cost

        project_costs["total_cost"] += call_cost

        if not _save_costs(project_id, project_costs, user_id=user_id):
            logger.warning("Failed to save image-gen costs for project %s", project_id)
            return None

        # Roll into per-user period spend so spending limits cover image gen too.
        resolved_user_id = user_id
        if not resolved_user_id:
            try:
                ps = _get_project_service()
                resolved_user_id = ps.get_project_owner_id(project_id)
            except Exception:
                pass
        if resolved_user_id:
            record_user_period_spend(resolved_user_id, call_cost)

        return project_costs


def _is_period_expired(period_start: Optional[str], frequency: Optional[str]) -> bool:
    """Check if a spending period has expired based on the reset frequency.

    Delegates to the standardized schedule (`spending_schedule.is_period_expired`)
    which uses an env-driven anchor (default: Sunday 09:00 Asia/Kolkata) so all
    weekly users reset at the same wall-clock instant instead of drifting to
    whenever they were created.
    """
    from app.utils.spending_schedule import is_period_expired

    return is_period_expired(period_start, frequency)


def check_user_spending_limit(user_id: Optional[str]) -> Optional[str]:
    """
    Check if a user has exceeded their spending limit.

    Educational Note: Supports period-based resets (daily/weekly/monthly).
    When a reset_frequency is configured, checks period_spend instead of
    lifetime total. Auto-resets the period if expired.

    Args:
        user_id: The user UUID (None = no check, e.g. single-user mode)

    Returns:
        None if OK, or an error message string if over limit.
    """
    if not user_id:
        return None

    try:
        from app.services.data_services.user_service import get_user_service
        from datetime import datetime
        svc = get_user_service()
        settings = svc.get_user_settings_raw(user_id)
        if not settings:
            return None

        cost_limit = settings.get("cost_limit")
        if cost_limit is None:
            return None  # No limit set = unlimited

        reset_frequency = settings.get("reset_frequency")

        if reset_frequency:
            # Period-based checking
            period_start = settings.get("period_start")
            period_spend = settings.get("period_spend", 0.0)

            # Auto-reset if period expired. Realigns to the most recent
            # anchor (default: Sunday 09:00 Asia/Kolkata) instead of
            # `now`, so every user with the same frequency stays in
            # lockstep for the next reset.
            if _is_period_expired(period_start, reset_frequency):
                from app.utils.spending_schedule import aligned_period_start_iso

                settings["period_spend"] = 0.0
                settings["period_start"] = aligned_period_start_iso(reset_frequency)
                svc.save_user_settings(user_id, settings)
                period_spend = 0.0

            if period_spend >= cost_limit:
                return (
                    f"You've reached your {reset_frequency} spending limit of ${cost_limit:.2f}. "
                    f"Current period spend: ${period_spend:.2f}. "
                    f"Contact your admin to increase it."
                )
        else:
            # Lifetime checking (no reset frequency)
            total_spend = svc.get_user_total_spend(user_id)
            if total_spend >= cost_limit:
                return (
                    f"You've reached your spending limit of ${cost_limit:.2f}. "
                    f"Current spend: ${total_spend:.2f}. Contact your admin to increase it."
                )

        return None
    except Exception as e:
        logger.error("Error checking spending limit for %s: %s", user_id, e)
        return None  # Fail open — don't block on errors


def record_user_only_usage(
    user_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """
    Track an API call against a user's period spend without a project.

    Workspace-level admin operations (e.g. design.md bootstrap) have no
    project to attribute cost to, so they don't show up in per-project
    cost dashboards. This still counts the call against the user's
    spending limit / period_spend so it can't be abused to bypass quotas.

    Returns the computed cost for the call (0.0 if untracked).
    """
    if not user_id:
        return 0.0
    model_key = _get_model_key(model)
    cost = _calculate_cost(
        model_key,
        input_tokens,
        output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
    )
    if cost > 0:
        record_user_period_spend(user_id, cost)
    return cost


def record_user_period_spend(user_id: Optional[str], call_cost: float) -> None:
    """
    Increment the user's period_spend after a successful API call.

    Educational Note: Only fires when the user has a cost_limit with
    a reset_frequency. Called from add_usage() alongside project/chat
    cost updates.
    """
    if not user_id or call_cost <= 0:
        return
    try:
        from app.services.data_services.user_service import get_user_service
        svc = get_user_service()
        svc.increment_period_spend(user_id, call_cost)
    except Exception as e:
        logger.error("Error recording period spend for %s: %s", user_id, e)


def get_project_costs(project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get cost tracking data for a project.

    Args:
        project_id: The project UUID

    Returns:
        Cost tracking data or default structure if not found
    """
    costs = _load_costs(project_id, user_id=user_id)

    # Ensure structure exists (for projects created before cost tracking)
    costs = _ensure_cost_structure(costs)

    return costs
