"""
Tests for MixpanelService.events_after — cohort path analysis.

Verifies the two-pass /export aggregation produces correct ranked output
for the questions Claude is meant to answer through this tool.
"""
from typing import Iterable
from unittest.mock import patch

import pytest

from app.services.integrations.knowledge_bases.mixpanel.mixpanel_service import (
    MixpanelService,
)


def _evt(name: str, uid: str, ts: int) -> dict:
    """Mimic the Mixpanel /export NDJSON event shape."""
    return {"event": name, "properties": {"distinct_id": uid, "time": ts}}


@pytest.fixture
def configured_service():
    """A MixpanelService with config short-circuited to 'configured'."""
    svc = MixpanelService()
    svc._configured = True
    svc._auth = object()  # not used because _export_request is mocked
    svc._project_id = "12345"
    return svc


def _patch_export(svc: MixpanelService, *batches: Iterable[dict]):
    """
    Replace _export_request with a side-effect that returns the next batch
    on each call. events_after makes TWO calls (cohort window, then full
    window) so pass two batches.
    """
    iterator = iter(batches)
    return patch.object(
        svc,
        "_export_request",
        side_effect=lambda from_date, to_date: iter(next(iterator)),
    )


# ==========================================================================
# Happy path
# ==========================================================================


class TestEventsAfterHappyPath:

    def test_ranks_post_trigger_events_by_distinct_users(self, configured_service):
        """
        3 cohort users (alice, bob, carol) all fire UPI on day 1.
        Then:
          - alice fires Open App, Send Money
          - bob fires Open App
          - carol fires Send Money, View Receipt
        Expected ranking: Open App (2), Send Money (2), View Receipt (1).
        Tie-break order between Open App and Send Money is implementation-
        defined; assert both are in top-2 with users=2.
        """
        # Pass 1 events: only the trigger event needs to appear in the
        # cohort window for this pass to populate the cohort dict.
        cohort_window = [
            _evt("UPI Addition", "alice", 1_700_000_000),
            _evt("UPI Addition", "bob",   1_700_000_100),
            _evt("UPI Addition", "carol", 1_700_000_200),
        ]
        # Pass 2 events: full export window incl. forward buffer.
        full_window = [
            _evt("UPI Addition", "alice", 1_700_000_000),  # excluded by default
            _evt("Open App",     "alice", 1_700_000_500),  # +500s — in window
            _evt("Send Money",   "alice", 1_700_001_000),
            _evt("UPI Addition", "bob",   1_700_000_100),
            _evt("Open App",     "bob",   1_700_000_700),
            _evt("UPI Addition", "carol", 1_700_000_200),
            _evt("Send Money",   "carol", 1_700_000_900),
            _evt("View Receipt", "carol", 1_700_001_100),
        ]

        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="UPI Addition",
                from_date="2024-01-01",
                to_date="2024-01-07",
                window_hours=24,
            )

        assert result["success"] is True
        data = result["data"]
        assert data["cohort_size"] == 3
        # Top three event names should be Open App, Send Money, View Receipt.
        names = [row["event"] for row in data["top_events"]]
        assert set(names[:2]) == {"Open App", "Send Money"}
        assert names[2] == "View Receipt"
        # Percentages computed against cohort_size=3
        users_by_name = {row["event"]: row["users"] for row in data["top_events"]}
        assert users_by_name["Open App"] == 2
        assert users_by_name["Send Money"] == 2
        assert users_by_name["View Receipt"] == 1
        pct_by_name = {row["event"]: row["pct_of_cohort"] for row in data["top_events"]}
        assert pct_by_name["Open App"] == pytest.approx(66.7, abs=0.1)
        assert pct_by_name["View Receipt"] == pytest.approx(33.3, abs=0.1)

    def test_excludes_trigger_event_by_default(self, configured_service):
        """Re-firing the trigger inside the forward window shouldn't show up."""
        cohort_window = [_evt("Signup", "alice", 1_000)]
        full_window = [
            _evt("Signup", "alice", 1_000),
            _evt("Signup", "alice", 2_000),  # second fire — exclude
            _evt("Onboard", "alice", 3_000),
        ]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="Signup",
                from_date="2024-01-01",
                to_date="2024-01-01",
                window_hours=24,
            )
        names = [r["event"] for r in result["data"]["top_events"]]
        assert "Signup" not in names
        assert names == ["Onboard"]

    def test_can_include_trigger_when_requested(self, configured_service):
        cohort_window = [_evt("Signup", "alice", 1_000)]
        full_window = [
            _evt("Signup", "alice", 1_000),
            _evt("Signup", "alice", 2_000),
            _evt("Onboard", "alice", 3_000),
        ]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="Signup",
                from_date="2024-01-01",
                to_date="2024-01-01",
                window_hours=24,
                exclude_trigger=False,
            )
        users_by_name = {r["event"]: r["users"] for r in result["data"]["top_events"]}
        assert users_by_name == {"Signup": 1, "Onboard": 1}


# ==========================================================================
# Edge cases
# ==========================================================================


class TestEventsAfterEdgeCases:

    def test_empty_cohort_returns_zero(self, configured_service):
        """Trigger event never fires in the cohort window."""
        cohort_window = []  # nothing
        full_window = [_evt("Open App", "alice", 1_000)]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="UPI Addition",
                from_date="2024-01-01",
                to_date="2024-01-07",
                window_hours=24,
            )
        assert result["success"] is True
        assert result["data"]["cohort_size"] == 0
        assert result["data"]["top_events"] == []

    def test_event_outside_window_is_ignored(self, configured_service):
        """An event later than window_hours after the trigger shouldn't count."""
        cohort_window = [_evt("Trigger", "alice", 1_000)]
        full_window = [
            _evt("Trigger", "alice", 1_000),
            _evt("Late Event", "alice", 1_000 + 25 * 3600),  # 25h later
        ]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="Trigger",
                from_date="2024-01-01",
                to_date="2024-01-01",
                window_hours=24,  # only events within 24h count
            )
        assert result["data"]["top_events"] == []

    def test_event_before_trigger_is_ignored(self, configured_service):
        """An event firing BEFORE the user's trigger doesn't count as 'after'."""
        cohort_window = [_evt("Trigger", "alice", 1_000)]
        full_window = [
            _evt("Pre Event", "alice", 500),  # before trigger
            _evt("Trigger", "alice", 1_000),
            _evt("Post Event", "alice", 1_500),
        ]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="Trigger",
                from_date="2024-01-01",
                to_date="2024-01-01",
                window_hours=24,
            )
        names = [r["event"] for r in result["data"]["top_events"]]
        assert names == ["Post Event"]

    def test_earliest_trigger_anchors_window(self, configured_service):
        """If a user fires the trigger twice, the earlier ts anchors the window."""
        cohort_window = [
            _evt("Trigger", "alice", 1_000),
            _evt("Trigger", "alice", 5_000),  # second fire
        ]
        full_window = [
            _evt("Trigger", "alice", 1_000),
            _evt("Trigger", "alice", 5_000),
            # 2_000s after EARLIEST trigger (1_000) → in 24h window
            _evt("Mid Event", "alice", 3_000),
        ]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="Trigger",
                from_date="2024-01-01",
                to_date="2024-01-01",
                window_hours=24,
            )
        names = [r["event"] for r in result["data"]["top_events"]]
        assert "Mid Event" in names

    def test_top_n_limits_output(self, configured_service):
        cohort_window = [_evt("Trigger", "alice", 1_000)]
        full_window = [
            _evt("Trigger", "alice", 1_000),
            *[_evt(f"Event{i}", "alice", 1_000 + i + 1) for i in range(10)],
        ]
        with _patch_export(configured_service, cohort_window, full_window):
            result = configured_service.events_after(
                trigger_event="Trigger",
                from_date="2024-01-01",
                to_date="2024-01-01",
                window_hours=24,
                top_n=3,
            )
        assert len(result["data"]["top_events"]) == 3


# ==========================================================================
# Validation
# ==========================================================================


class TestEventsAfterValidation:

    def test_missing_trigger_event_errors(self, configured_service):
        result = configured_service.events_after(
            trigger_event="",
            from_date="2024-01-01",
            to_date="2024-01-07",
        )
        assert result["success"] is False
        assert "trigger_event" in result["error"]

    def test_missing_dates_errors(self, configured_service):
        result = configured_service.events_after(
            trigger_event="X",
            from_date="",
            to_date="",
        )
        assert result["success"] is False

    def test_invalid_date_format_errors(self, configured_service):
        result = configured_service.events_after(
            trigger_event="X",
            from_date="not-a-date",
            to_date="2024-01-07",
        )
        assert result["success"] is False

    def test_zero_window_hours_errors(self, configured_service):
        result = configured_service.events_after(
            trigger_event="X",
            from_date="2024-01-01",
            to_date="2024-01-07",
            window_hours=0,
        )
        assert result["success"] is False

    def test_zero_top_n_errors(self, configured_service):
        """top_n=0 must error rather than silently returning an empty list —
        otherwise a successful run looks like 'no events found'."""
        result = configured_service.events_after(
            trigger_event="X",
            from_date="2024-01-01",
            to_date="2024-01-07",
            top_n=0,
        )
        assert result["success"] is False
        assert "top_n" in result["error"]
