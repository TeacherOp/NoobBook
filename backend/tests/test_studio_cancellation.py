"""
Tests for cooperative studio-job cancellation.

Covers the three layers from the design:
  Layer 1: raise_if_cancelled trips on either signal source (in-memory
           task_service set OR studio_jobs.status = "cancelled").
  Layer 2a: with_failure_guard preserves cancelled status when the
            wrapped function raises StudioJobCancelled.
  Layer 2b: update_job refuses any non-cancelled status update over an
            already-cancelled row (clobber-protection).
"""
from unittest.mock import patch

import pytest

from app.services.background_services import task_service
from app.services.studio_services import studio_index_service
from app.services.studio_services.studio_index_service import StudioJobCancelled


# task_service.is_target_cancelled is a METHOD on the singleton instance,
# not a module-level function — so the string-path `patch("...task_service.
# is_target_cancelled")` fails to resolve. patch.object on the singleton is
# the correct mock for these tests.


# ==========================================================================
# Layer 1 — raise_if_cancelled
# ==========================================================================


class TestRaiseIfCancelled:

    def test_no_cancel_is_noop(self):
        """Neither signal active → raise_if_cancelled returns silently."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "processing"},
        ):
            studio_index_service.raise_if_cancelled("p1", "j1")  # no exception

    def test_in_memory_set_trips(self):
        """task_service._cancelled_tasks set hit → raises immediately."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=True,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "processing"},
        ):
            with pytest.raises(StudioJobCancelled):
                studio_index_service.raise_if_cancelled("p1", "j1")

    def test_db_status_cancelled_trips(self):
        """In-memory set miss but DB row says cancelled → still raises.
        Covers the cross-process case (cancel issued from a different
        pod / after a worker restart)."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "cancelled"},
        ):
            with pytest.raises(StudioJobCancelled):
                studio_index_service.raise_if_cancelled("p1", "j1")

    def test_missing_job_is_noop(self):
        """get_job returns None (job deleted concurrently) → don't raise.
        The route would have returned 404 to the user; the worker should
        finish or fail naturally rather than throwing on a phantom cancel."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=None,
        ):
            studio_index_service.raise_if_cancelled("p1", "j1")  # no exception


# ==========================================================================
# Layer 2a — with_failure_guard preserves cancelled
# ==========================================================================


class TestWithFailureGuardCancelHandling:

    def test_studio_job_cancelled_does_not_call_update(self):
        """When the wrapped function raises StudioJobCancelled, the guard
        must NOT call update_job(status='error') — the cancel route
        already wrote status='cancelled' and we don't want to clobber."""
        def cancelled_worker(*, project_id, job_id, **_):
            raise StudioJobCancelled("user clicked stop")

        wrapped = studio_index_service.with_failure_guard(cancelled_worker)
        with patch(
            "app.services.studio_services.studio_index_service.update_job"
        ) as mock_update:
            with pytest.raises(StudioJobCancelled):
                wrapped(project_id="p1", job_id="j1")
        mock_update.assert_not_called()

    def test_other_exceptions_still_flip_to_error(self):
        """Non-cancellation exceptions still get the existing 'error'
        treatment so the chat surface can show a useful message."""
        def crashing_worker(*, project_id, job_id, **_):
            raise RuntimeError("boom")

        wrapped = studio_index_service.with_failure_guard(crashing_worker)
        with patch(
            "app.services.studio_services.studio_index_service.update_job"
        ) as mock_update, patch(
            "app.services.studio_services.studio_index_service.is_job_cancelled",
            return_value=False,
        ):
            with pytest.raises(RuntimeError):
                wrapped(project_id="p1", job_id="j1")
        mock_update.assert_called_once()
        # The status set on the row is 'error', not 'cancelled'.
        kwargs = mock_update.call_args.kwargs
        assert kwargs.get("status") == "error"

    def test_crash_after_cancel_preserves_cancelled(self):
        """If the worker crashes AFTER the user clicked Stop (race
        condition: cancel signal arrived but the worker hadn't checked
        yet, then a different unrelated exception happened), still don't
        overwrite the cancelled marker."""
        def crashing_worker(*, project_id, job_id, **_):
            raise RuntimeError("boom")

        wrapped = studio_index_service.with_failure_guard(crashing_worker)
        with patch(
            "app.services.studio_services.studio_index_service.update_job"
        ) as mock_update, patch(
            "app.services.studio_services.studio_index_service.is_job_cancelled",
            return_value=True,
        ):
            with pytest.raises(RuntimeError):
                wrapped(project_id="p1", job_id="j1")
        mock_update.assert_not_called()


# ==========================================================================
# Layer 2b — update_job clobber-protection
# ==========================================================================


class TestUpdateJobClobberProtection:

    def test_refuses_to_overwrite_cancelled_with_ready(self):
        """Worker raced the cancel and tried to flip to 'ready' after the
        cancel route already wrote 'cancelled'. The clobber check should
        no-op the update so the cancelled marker survives."""
        cancelled_row = {"id": "j1", "project_id": "p1", "status": "cancelled"}
        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=cancelled_row,
        ) as mock_get, patch(
            "app.services.studio_services.studio_index_service._get_client"
        ) as mock_client:
            result = studio_index_service.update_job(
                "p1", "j1", status="ready", progress="Complete",
            )
        # Returned the existing cancelled row, never hit Supabase write.
        assert result == cancelled_row
        mock_client.assert_not_called()
        mock_get.assert_called_once()

    def test_refuses_to_overwrite_cancelled_with_error(self):
        """Same protection against status='error' (e.g. an executor
        outside with_failure_guard catches its own exception and tries
        to flip the row)."""
        cancelled_row = {"id": "j1", "project_id": "p1", "status": "cancelled"}
        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=cancelled_row,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client"
        ) as mock_client:
            result = studio_index_service.update_job(
                "p1", "j1", status="error", error="something broke",
            )
        assert result == cancelled_row
        mock_client.assert_not_called()

    def test_refuses_to_overwrite_ready_with_cancelled(self):
        """Race: worker finished and wrote status='ready' in the gap
        between the cancel route's initial get_job (saw 'processing',
        so it didn't early-exit) and its update_job(status='cancelled').
        Without this guard the cancel route would silently flip a
        completed job to cancelled, hiding output the user already paid
        for."""
        ready_row = {"id": "j1", "project_id": "p1", "status": "ready",
                     "audio_url": "/api/v1/.../out.mp3"}
        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=ready_row,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client"
        ) as mock_client:
            result = studio_index_service.update_job(
                "p1", "j1",
                status="cancelled",
                error="Cancelled by user",
            )
        assert result == ready_row
        mock_client.assert_not_called()

    def test_refuses_to_overwrite_error_with_cancelled(self):
        """Same race as above, just with the worker error path. A
        cancel arriving immediately after a real failure shouldn't
        relabel the failure as a user cancellation."""
        error_row = {"id": "j1", "project_id": "p1", "status": "error",
                     "error_message": "API timeout"}
        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=error_row,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client"
        ) as mock_client:
            result = studio_index_service.update_job(
                "p1", "j1", status="cancelled",
            )
        assert result == error_row
        mock_client.assert_not_called()

    def test_allows_re_cancel_idempotent(self):
        """Updating cancelled → cancelled is allowed (idempotent re-cancel
        from the route, e.g. the user double-clicked Stop)."""
        cancelled_row = {"id": "j1", "project_id": "p1", "status": "cancelled"}

        # When the new status IS cancelled, the clobber check skips and
        # the function proceeds to the normal write path. We mock the
        # Supabase call so the test doesn't need a real client.
        class _FakeResp:
            data = [cancelled_row]

        class _FakeBuilder:
            def update(self, _payload):
                return self
            def eq(self, *_, **__):
                return self
            def execute(self):
                return _FakeResp()

        class _FakeClient:
            def table(self, _name):
                return _FakeBuilder()

        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=cancelled_row,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client",
            return_value=_FakeClient(),
        ), patch(
            "app.services.studio_services.studio_index_service._map_job",
            return_value=cancelled_row,
        ):
            result = studio_index_service.update_job(
                "p1", "j1", status="cancelled", error="Cancelled by user",
            )
        assert result == cancelled_row
