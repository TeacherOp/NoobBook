"""
Cost Tracking Utility - Track and calculate API costs per project.

Educational Note: This utility tracks Claude API usage costs by model.
Costs are stored in Supabase projects table and updated after each API call.

Pricing (per 1M tokens):
- Sonnet: $3 input, $15 output
- Haiku: $1 input, $5 output
"""
from typing import Dict, Any, Optional
from threading import Lock


# Pricing per 1M tokens
PRICING = {
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 1.0, "output": 5.0},
}

# Lock for thread-safe operations
_lock = Lock()


def _get_model_key(model_string: str) -> str:
    """
    Extract model key (sonnet/haiku) from full model string.

    Args:
        model_string: Full model ID like "claude-sonnet-4-5-20250929"

    Returns:
        "sonnet" or "haiku"
    """
    model_lower = model_string.lower()
    if "sonnet" in model_lower:
        return "sonnet"
    elif "haiku" in model_lower:
        return "haiku"
    else:
        # Default to sonnet pricing for unknown models
        return "sonnet"


def _calculate_cost(model_key: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for a single API call.

    Args:
        model_key: "sonnet" or "haiku"
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    pricing = PRICING.get(model_key, PRICING["sonnet"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def _get_project_service():
    """Get project service (lazy import to avoid circular imports)."""
    from app.services.data_services import project_service
    return project_service


def _load_costs(project_id: str) -> Optional[Dict[str, Any]]:
    """Load cost tracking data from Supabase."""
    try:
        return _get_project_service().get_project_costs(project_id)
    except Exception as e:
        print(f"Cost tracking: Error loading costs for {project_id}: {e}")
        return None


def _save_costs(project_id: str, costs: Dict[str, Any]) -> bool:
    """Save cost tracking data to Supabase."""
    try:
        return _get_project_service().update_project_costs(project_id, costs)
    except Exception as e:
        print(f"Cost tracking: Error saving costs for {project_id}: {e}")
        return False


def _get_default_costs() -> Dict[str, Any]:
    """
    Get default cost tracking structure.

    Educational Note: Returns the initial cost tracking structure
    for projects that don't have costs yet.
    """
    return {
        "total_cost": 0.0,
        "by_model": {
            "sonnet": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            },
            "haiku": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            }
        }
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
    if "by_model" not in costs:
        costs["by_model"] = {}

    for model in ["sonnet", "haiku"]:
        if model not in costs["by_model"]:
            costs["by_model"][model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            }

    return costs


def add_usage(
    project_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int
) -> Optional[Dict[str, Any]]:
    """
    Add API usage to project cost tracking.

    Educational Note: This function is called after each Claude API call
    to update the cumulative cost tracking in Supabase.

    Args:
        project_id: The project UUID
        model: Full model string (e.g., "claude-sonnet-4-5-20250929")
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used

    Returns:
        Updated cost tracking data or None if failed
    """
    with _lock:
        # Load current costs from Supabase
        costs = _load_costs(project_id)
        if costs is None:
            # Project might not exist or no costs yet - use defaults
            costs = _get_default_costs()

        # Ensure structure exists
        costs = _ensure_cost_structure(costs)

        # Get model key and calculate cost
        model_key = _get_model_key(model)
        call_cost = _calculate_cost(model_key, input_tokens, output_tokens)

        # Update model-specific tracking
        model_tracking = costs["by_model"][model_key]
        model_tracking["input_tokens"] += input_tokens
        model_tracking["output_tokens"] += output_tokens
        model_tracking["cost"] += call_cost

        # Update total cost
        costs["total_cost"] += call_cost

        # Save updated costs to Supabase
        if _save_costs(project_id, costs):
            return costs
        else:
            print(f"Cost tracking: Failed to save costs for project {project_id}")
            return None


def get_project_costs(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cost tracking data for a project.

    Args:
        project_id: The project UUID

    Returns:
        Cost tracking data or default structure if not found
    """
    costs = _load_costs(project_id)

    # Ensure structure exists (for projects created before cost tracking)
    costs = _ensure_cost_structure(costs)

    return costs
