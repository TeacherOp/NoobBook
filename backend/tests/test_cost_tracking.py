"""
Tests for cost_tracking.py.

Covers:
- _get_model_key: model string detection, case insensitivity, unknown defaults
- _calculate_cost: exact pricing math for sonnet/haiku
- _ensure_cost_structure: None, empty, partial dicts, preserves existing
- _get_default_costs: structure validation
"""
import pytest

from app.utils.cost_tracking import (
    _get_model_key,
    _calculate_cost,
    _calculate_cache_savings,
    _apply_usage,
    _get_default_costs,
    _ensure_cost_structure,
)


# ===========================================================================
# _get_model_key
# ===========================================================================

class TestGetModelKey:

    def test_sonnet_full_id(self):
        assert _get_model_key("claude-sonnet-4-5-20250929") == "sonnet"

    def test_haiku_full_id(self):
        assert _get_model_key("claude-haiku-3-20240307") == "haiku"

    def test_sonnet_short(self):
        assert _get_model_key("claude-sonnet-4-6") == "sonnet"

    def test_haiku_short(self):
        assert _get_model_key("claude-haiku-4-5") == "haiku"

    def test_case_insensitive(self):
        assert _get_model_key("claude-SONNET-4-6") == "sonnet"
        assert _get_model_key("CLAUDE-HAIKU-3") == "haiku"

    def test_unknown_defaults_to_sonnet(self):
        """Unknown model strings default to sonnet pricing."""
        assert _get_model_key("gpt-4o") == "sonnet"
        assert _get_model_key("unknown-model") == "sonnet"

    def test_empty_string(self):
        assert _get_model_key("") == "sonnet"


# ===========================================================================
# _calculate_cost
# ===========================================================================

class TestCalculateCost:

    def test_sonnet_input_only(self):
        """Sonnet: $3/1M input tokens → 1M tokens = $3.00"""
        assert _calculate_cost("sonnet", 1_000_000, 0) == pytest.approx(3.0)

    def test_sonnet_output_only(self):
        """Sonnet: $15/1M output tokens → 1M tokens = $15.00"""
        assert _calculate_cost("sonnet", 0, 1_000_000) == pytest.approx(15.0)

    def test_sonnet_combined(self):
        """Sonnet: 1M in + 1M out = $3 + $15 = $18"""
        assert _calculate_cost("sonnet", 1_000_000, 1_000_000) == pytest.approx(18.0)

    def test_haiku_input_only(self):
        """Haiku: $1/1M input tokens"""
        assert _calculate_cost("haiku", 1_000_000, 0) == pytest.approx(1.0)

    def test_haiku_output_only(self):
        """Haiku: $5/1M output tokens"""
        assert _calculate_cost("haiku", 0, 1_000_000) == pytest.approx(5.0)

    def test_haiku_combined(self):
        """Haiku: 1M in + 1M out = $1 + $5 = $6"""
        assert _calculate_cost("haiku", 1_000_000, 1_000_000) == pytest.approx(6.0)

    def test_zero_tokens(self):
        assert _calculate_cost("sonnet", 0, 0) == 0.0

    def test_small_usage(self):
        """1000 tokens should cost fractions of a cent."""
        cost = _calculate_cost("sonnet", 1000, 1000)
        assert cost == pytest.approx(0.018, abs=0.001)

    def test_unknown_model_uses_sonnet_pricing(self):
        """Unknown model key falls back to sonnet pricing."""
        # Use a clearly-fictitious model key — "opus" is a real entry in
        # PRICING now, so it would no longer exercise the fallback path.
        assert _calculate_cost("nonexistent-model", 1_000_000, 0) == pytest.approx(3.0)


# ===========================================================================
# _get_default_costs
# ===========================================================================

class TestGetDefaultCosts:

    def test_structure(self):
        costs = _get_default_costs()
        assert costs["total_cost"] == 0.0
        assert "sonnet" in costs["by_model"]
        assert "haiku" in costs["by_model"]

    def test_model_structure(self):
        costs = _get_default_costs()
        for model in ["sonnet", "haiku"]:
            assert costs["by_model"][model]["input_tokens"] == 0
            assert costs["by_model"][model]["output_tokens"] == 0
            assert costs["by_model"][model]["cost"] == 0.0
            assert costs["by_model"][model]["cache_creation_tokens"] == 0
            assert costs["by_model"][model]["cache_read_tokens"] == 0

    def test_cache_savings_present(self):
        assert _get_default_costs()["cache_savings"] == 0.0


# ===========================================================================
# _ensure_cost_structure
# ===========================================================================

class TestEnsureCostStructure:

    def test_none_returns_defaults(self):
        result = _ensure_cost_structure(None)
        assert result["total_cost"] == 0.0
        assert "sonnet" in result["by_model"]
        assert "haiku" in result["by_model"]

    def test_empty_dict_fills_all(self):
        result = _ensure_cost_structure({})
        assert result["total_cost"] == 0.0
        assert "sonnet" in result["by_model"]

    def test_partial_dict_missing_model(self):
        """Dict with sonnet but missing haiku gets haiku added."""
        costs = {
            "total_cost": 5.0,
            "by_model": {
                "sonnet": {"input_tokens": 100, "output_tokens": 50, "cost": 5.0}
            }
        }
        result = _ensure_cost_structure(costs)
        assert result["total_cost"] == 5.0
        assert result["by_model"]["sonnet"]["cost"] == 5.0
        assert result["by_model"]["haiku"]["cost"] == 0.0

    def test_preserves_existing_values(self):
        """Existing non-zero values are not overwritten."""
        costs = {
            "total_cost": 10.5,
            "by_model": {
                "sonnet": {"input_tokens": 500, "output_tokens": 200, "cost": 10.5},
                "haiku": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            }
        }
        result = _ensure_cost_structure(costs)
        assert result["total_cost"] == 10.5
        assert result["by_model"]["sonnet"]["input_tokens"] == 500

    def test_missing_total_cost(self):
        costs = {"by_model": {"sonnet": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}}}
        result = _ensure_cost_structure(costs)
        assert result["total_cost"] == 0.0

    def test_missing_by_model(self):
        costs = {"total_cost": 0.0}
        result = _ensure_cost_structure(costs)
        assert "sonnet" in result["by_model"]
        assert "haiku" in result["by_model"]

    def test_backfills_cache_fields_for_legacy_buckets(self):
        """Projects created before cache tracking get the new fields seeded to 0."""
        legacy = {
            "total_cost": 1.0,
            "by_model": {
                "sonnet": {"input_tokens": 100, "output_tokens": 50, "cost": 1.0},
            },
        }
        result = _ensure_cost_structure(legacy)
        assert result["by_model"]["sonnet"]["cache_creation_tokens"] == 0
        assert result["by_model"]["sonnet"]["cache_read_tokens"] == 0
        # Legacy values must still be preserved.
        assert result["by_model"]["sonnet"]["input_tokens"] == 100
        assert result["cache_savings"] == 0.0


# ===========================================================================
# Cache-aware cost math
# ===========================================================================

class TestCalculateCostWithCache:

    def test_cache_creation_is_125_percent_of_input(self):
        """1M creation tokens at sonnet's $3 input rate = $3.75 (1.25×)."""
        assert _calculate_cost("sonnet", 0, 0, cache_creation_tokens=1_000_000) == pytest.approx(3.75)

    def test_cache_read_is_10_percent_of_input(self):
        """1M read tokens at sonnet's $3 input rate = $0.30 (0.1×)."""
        assert _calculate_cost("sonnet", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.30)

    def test_full_call_with_cache(self):
        """Regular input + output + creation + read all sum together."""
        # sonnet: input=$3, output=$15
        # 100k input ($0.30) + 200k output ($3) + 50k creation ($0.1875) + 500k read ($0.15)
        cost = _calculate_cost(
            "sonnet",
            input_tokens=100_000,
            output_tokens=200_000,
            cache_creation_tokens=50_000,
            cache_read_tokens=500_000,
        )
        assert cost == pytest.approx(0.30 + 3.0 + 0.1875 + 0.15)

    def test_haiku_cache_pricing(self):
        """Haiku input rate is $1/1M → creation = $1.25, read = $0.10."""
        assert _calculate_cost("haiku", 0, 0, cache_creation_tokens=1_000_000) == pytest.approx(1.25)
        assert _calculate_cost("haiku", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.10)

    def test_legacy_call_without_cache_args_unchanged(self):
        """Existing callers that pass only input/output get identical math."""
        assert _calculate_cost("sonnet", 1_000_000, 1_000_000) == pytest.approx(18.0)


class TestCacheSavings:

    def test_pure_read_savings_is_90_percent_of_input_rate(self):
        """1M sonnet reads save (1 − 0.1) × $3 = $2.70 vs uncached billing."""
        assert _calculate_cache_savings("sonnet", 0, 1_000_000) == pytest.approx(2.70)

    def test_pure_creation_is_negative_25_percent_premium(self):
        """1M sonnet writes cost an extra (1.25 − 1) × $3 = $0.75 over uncached."""
        assert _calculate_cache_savings("sonnet", 1_000_000, 0) == pytest.approx(-0.75)

    def test_amortized_after_a_few_reads(self):
        """After one write + 4 reads the math should be net positive."""
        # 100k creation → -$0.075 premium; 4×100k read → +4×$0.27 = $1.08 gain
        result = _calculate_cache_savings("sonnet", 100_000, 400_000)
        assert result == pytest.approx(-0.075 + 1.08)


class TestApplyUsage:

    def _fresh(self):
        return _get_default_costs()

    def test_records_cache_token_counts(self):
        costs = self._fresh()
        _apply_usage(
            costs,
            "claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cache_creation_tokens=2000,
            cache_read_tokens=8000,
        )
        bucket = costs["by_model"]["sonnet"]
        assert bucket["cache_creation_tokens"] == 2000
        assert bucket["cache_read_tokens"] == 8000

    def test_accumulates_across_calls(self):
        costs = self._fresh()
        for _ in range(3):
            _apply_usage(
                costs,
                "claude-sonnet-4-6",
                input_tokens=0,
                output_tokens=0,
                cache_read_tokens=100_000,
            )
        assert costs["by_model"]["sonnet"]["cache_read_tokens"] == 300_000

    def test_cache_savings_aggregates(self):
        """Top-level cache_savings rolls up net savings across calls."""
        costs = self._fresh()
        _apply_usage(
            costs,
            "claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=1_000_000,  # +$2.70 saved
        )
        _apply_usage(
            costs,
            "claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=1_000_000,  # -$0.75 premium
        )
        assert costs["cache_savings"] == pytest.approx(2.70 - 0.75)

    def test_legacy_call_signature_still_works(self):
        """Callers passing only input/output (no cache args) still update correctly."""
        costs = self._fresh()
        _apply_usage(costs, "claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        bucket = costs["by_model"]["sonnet"]
        assert bucket["input_tokens"] == 1000
        assert bucket["output_tokens"] == 500
        assert bucket["cache_creation_tokens"] == 0
        assert bucket["cache_read_tokens"] == 0
        assert costs["cache_savings"] == 0.0
