"""
Tests for the logs viewer tail-read path.

Covers the new ``_tail_lines`` backward-block reader plus the
``_get_recent_lines`` wrapper that hands back to ``_read_recent_lines``
on unexpected errors. The whole-file reader is exercised via the
fallback path so it stays green too.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

# Importing the routes module triggers the broader app import chain;
# stub the Supabase env so the supabase client doesn't refuse to
# initialise. Mirrors the pattern in test_log_housekeeping.
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoidGVzdCJ9.test",
)

import pytest

from app.api.logs import routes as logs_routes
from app.utils import logger as logger_module


_ERROR_LEVELS = {"ERROR", "CRITICAL"}
_WARN_LEVELS = {"WARNING", "ERROR", "CRITICAL"}
_ALL_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _write_log(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _entry(level: str, ts: str, msg: str, *, logger_name: str = "app.foo") -> str:
    return f"{ts} [{level}] {logger_name} [req:abc12345]: {msg}"


class TestTailLines:
    """Backward-block reader: O(requested) instead of O(file size)."""

    def test_returns_last_n_anchors_chronological(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("INFO", "10:00:00", "boot"),
                _entry("ERROR", "10:00:01", "first error"),
                _entry("INFO", "10:00:02", "noise"),
                _entry("ERROR", "10:00:03", "second error"),
                _entry("WARNING", "10:00:04", "warned"),
                _entry("ERROR", "10:00:05", "third error"),
            ],
        )
        result = logs_routes._tail_lines(path, limit=2, levels=_ERROR_LEVELS)
        assert [e["ts"] for e in result] == ["10:00:03", "10:00:05"]
        assert all(e["level"] == "ERROR" for e in result)

    def test_stitches_multi_line_stack_trace(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("INFO", "10:00:00", "ok"),
                _entry("ERROR", "10:00:01", "boom"),
                'Traceback (most recent call last):',
                '  File "x.py", line 1, in <module>',
                "    raise RuntimeError('bad')",
                "RuntimeError: bad",
                _entry("INFO", "10:00:02", "carrying on"),
            ],
        )
        result = logs_routes._tail_lines(path, limit=10, levels=_ERROR_LEVELS)
        assert len(result) == 1
        msg = result[0]["message"]
        assert "boom" in msg
        assert "Traceback" in msg
        assert "RuntimeError: bad" in msg

    def test_since_param_returns_only_newer_entries(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("ERROR", "10:00:01", "old"),
                _entry("ERROR", "10:00:02", "older still"),
                _entry("ERROR", "10:00:03", "new one"),
                _entry("ERROR", "10:00:04", "newest"),
            ],
        )
        result = logs_routes._tail_lines(
            path, limit=10, levels=_ERROR_LEVELS, since="10:00:02"
        )
        # "Strictly newer than" — 10:00:02 itself is excluded.
        assert [e["ts"] for e in result] == ["10:00:03", "10:00:04"]

    def test_level_filter_excludes_lower_levels(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("DEBUG", "10:00:00", "noise"),
                _entry("INFO", "10:00:01", "fyi"),
                _entry("WARNING", "10:00:02", "watch"),
                _entry("ERROR", "10:00:03", "ouch"),
            ],
        )
        only_errors = logs_routes._tail_lines(path, limit=10, levels=_ERROR_LEVELS)
        assert [e["level"] for e in only_errors] == ["ERROR"]

        warn_plus = logs_routes._tail_lines(path, limit=10, levels=_WARN_LEVELS)
        assert [e["level"] for e in warn_plus] == ["WARNING", "ERROR"]

    def test_empty_file_returns_empty_list(self, tmp_path):
        path = tmp_path / "backend.log"
        path.write_text("", encoding="utf-8")
        assert logs_routes._tail_lines(path, limit=10, levels=_ERROR_LEVELS) == []

    def test_limit_zero_returns_empty(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(path, [_entry("ERROR", "10:00:00", "x")])
        assert logs_routes._tail_lines(path, limit=0, levels=_ERROR_LEVELS) == []

    def test_reads_only_tail_blocks_for_large_file(self, tmp_path, monkeypatch):
        """With a small block size, a 50-line file should be readable
        with a single tail block when n=2 matches live in the last
        block — proving the reader is bounded by requested lines, not
        file size."""
        path = tmp_path / "backend.log"
        lines = [_entry("INFO", f"10:00:{i:02d}", f"chatter {i}") for i in range(48)]
        lines.append(_entry("ERROR", "10:00:48", "almost last"))
        lines.append(_entry("ERROR", "10:00:49", "last"))
        _write_log(path, lines)

        # Shrink the block size to force the reader to load several
        # blocks if it tried to read the whole file; the assert below
        # is that it reads at most a handful, not all 50 lines worth.
        monkeypatch.setattr(logs_routes, "_TAIL_BLOCK_BYTES", 256)

        read_block_count = 0
        real_read = Path.open

        def _counting_open(self, *args, **kwargs):
            handle = real_read(self, *args, **kwargs)
            inner_read = handle.read

            def _read(*a, **kw):
                nonlocal read_block_count
                data = inner_read(*a, **kw)
                if data:
                    read_block_count += 1
                return data

            handle.read = _read  # type: ignore[assignment]
            return handle

        with patch.object(Path, "open", _counting_open):
            result = logs_routes._tail_lines(
                path, limit=2, levels=_ERROR_LEVELS
            )

        assert [e["ts"] for e in result] == ["10:00:48", "10:00:49"]
        # Whole-file scan would need ceil(total_size / 256) reads
        # (~roughly the line count). A correct backward reader should
        # need just a few blocks to find both errors at the tail.
        assert read_block_count < 8, (
            f"Tail reader read {read_block_count} blocks for 2 matching "
            "lines — should be small, not whole-file."
        )


class TestMidnightWrap:
    """The log format stores HH:MM:SS without a date, so a naive
    lexical compare drops every post-midnight entry. ``_ts_strictly_after``
    treats a backwards gap of more than 12 h as a midnight rollover."""

    def test_post_midnight_entry_is_newer_than_pre_midnight_since(self):
        # 00:00:01 must be considered newer than 23:59:55.
        assert logs_routes._ts_strictly_after("00:00:01", "23:59:55") is True

    def test_same_day_lexical_compare_still_works(self):
        assert logs_routes._ts_strictly_after("10:00:05", "10:00:00") is True
        assert logs_routes._ts_strictly_after("10:00:00", "10:00:05") is False

    def test_small_backwards_gap_is_not_treated_as_wrap(self):
        # 23:59:50 is older than 23:59:55 (5 s gap), not a wrap.
        assert logs_routes._ts_strictly_after("23:59:50", "23:59:55") is False

    def test_tail_reader_returns_post_midnight_entries_after_wrap(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("ERROR", "23:59:30", "before"),
                _entry("ERROR", "23:59:55", "boundary"),
                _entry("ERROR", "00:00:01", "after midnight"),
                _entry("ERROR", "00:00:05", "later"),
            ],
        )
        result = logs_routes._tail_lines(
            path, limit=10, levels=_ERROR_LEVELS, since="23:59:55"
        )
        # Pure lexical compare would return [] because "00:00:01" <= "23:59:55".
        # Wrap-aware compare returns the two post-midnight entries.
        assert [e["message"] for e in result] == ["after midnight", "later"]


class TestCrossBlockStackTrace:
    """A stack trace spanning two 64 KB blocks must arrive intact —
    continuation lines that land at the start of a block (with their
    anchor in the previous, earlier block) must ride along as carry
    rather than being silently discarded."""

    def test_stack_trace_continuations_ride_carry_across_block_boundary(
        self, tmp_path, monkeypatch
    ):
        # Force a small block size so we can engineer the split exactly
        # at the middle of a stack-trace record.
        monkeypatch.setattr(logs_routes, "_TAIL_BLOCK_BYTES", 128)
        path = tmp_path / "backend.log"

        # Build a file where:
        #   - The anchor with the stack trace is "near the end" of the
        #     earlier block.
        #   - Several continuation lines land in the later block.
        #   - A separate anchor follows the continuation lines in the
        #     later block.
        # We pad with filler so the boundary lands inside the stack.
        filler = [_entry("INFO", f"09:{i:02d}:00", "filler line " * 4) for i in range(2)]
        stack_anchor = _entry("ERROR", "10:00:01", "boom: stack incoming")
        stack_lines = [
            "Traceback (most recent call last):",
            '  File "x.py", line 1, in <module>',
            "    raise RuntimeError('bad')",
            "RuntimeError: bad",
        ]
        trailing_anchor = _entry("INFO", "10:00:02", "carrying on")
        _write_log(path, filler + [stack_anchor, *stack_lines, trailing_anchor])

        result = logs_routes._tail_lines(
            path, limit=10, levels=_ERROR_LEVELS
        )
        assert len(result) == 1
        msg = result[0]["message"]
        # Every continuation line must be present — the previous bug
        # silently dropped continuations that landed at the start of
        # the later block.
        for needle in (
            "Traceback (most recent call last):",
            '  File "x.py", line 1, in <module>',
            "raise RuntimeError('bad')",
            "RuntimeError: bad",
        ):
            assert needle in msg, f"Missing continuation line: {needle!r}"


class TestGetRecentLinesFallback:
    """``_get_recent_lines`` should hand off to the whole-file scan
    when the tail reader raises — preserves the legacy behaviour."""

    def test_fallback_when_tail_raises(self, tmp_path, monkeypatch):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("ERROR", "10:00:00", "alpha"),
                _entry("ERROR", "10:00:01", "beta"),
            ],
        )
        monkeypatch.setattr(logger_module, "LOG_FILE", path)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated tail-reader bug")

        monkeypatch.setattr(logs_routes, "_tail_lines", _boom)
        result = logs_routes._get_recent_lines(10, _ERROR_LEVELS)
        assert [e["message"] for e in result] == ["alpha", "beta"]

    def test_returns_empty_when_log_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "LOG_FILE", tmp_path / "no-such.log")
        assert logs_routes._get_recent_lines(10, _ERROR_LEVELS) == []


class TestDatedTimestamps:
    """ISO-8601 ``YYYY-MM-DDTHH:MM:SS`` is the new on-disk format. The
    parser must still accept the legacy ``HH:MM:SS`` shape so rotated
    archives written before the change still display in the admin UI."""

    def test_line_re_parses_iso8601_timestamp(self):
        line = (
            "2026-05-20T14:27:44 [ERROR] app.foo "
            "[req:abc12345]: something went wrong"
        )
        m = logs_routes._LINE_RE.match(line)
        assert m is not None
        assert m.group("ts") == "2026-05-20T14:27:44"
        assert m.group("level") == "ERROR"
        assert m.group("logger") == "app.foo"
        assert m.group("req_id") == "abc12345"
        assert m.group("message") == "something went wrong"

    def test_line_re_still_parses_legacy_hms(self):
        line = "14:27:44 [ERROR] app.foo [req:abc12345]: legacy archive"
        m = logs_routes._LINE_RE.match(line)
        assert m is not None
        assert m.group("ts") == "14:27:44"
        assert m.group("message") == "legacy archive"

    def test_strictly_after_with_two_iso8601_no_wrap(self):
        # Lexical compare on ISO-8601 is correct — no midnight heuristic
        # needed when both sides carry a date.
        assert logs_routes._ts_strictly_after(
            "2026-05-21T00:00:01", "2026-05-20T23:59:55"
        ) is True
        assert logs_routes._ts_strictly_after(
            "2026-05-20T23:59:55", "2026-05-21T00:00:01"
        ) is False

    def test_strictly_after_mixed_iso_and_legacy(self):
        # Live tail across a deploy boundary: `since` was captured before
        # the format change, the next entry arrives in the new format.
        # Falls back to the wrap-tolerant time-of-day compare.
        # Dated `ts`, legacy `since` (deploy-boundary cursor) — newer
        # time-of-day must be treated as newer so the post-deploy entry
        # isn't black-holed.
        assert logs_routes._ts_strictly_after(
            "2026-05-20T10:00:05", "10:00:00"
        ) is True

    def test_tail_reader_reads_dated_log_file(self, tmp_path):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                f"2026-05-20T10:00:00 [ERROR] app.foo [req:r1]: alpha",
                f"2026-05-20T10:00:01 [ERROR] app.foo [req:r2]: beta",
            ],
        )
        result = logs_routes._tail_lines(path, limit=10, levels=_ERROR_LEVELS)
        assert [e["ts"] for e in result] == [
            "2026-05-20T10:00:00",
            "2026-05-20T10:00:01",
        ]
        assert [e["message"] for e in result] == ["alpha", "beta"]


class TestReadRecentLinesLegacy:
    """The whole-file fallback should still honour the new ``since`` arg."""

    def test_since_filter_in_legacy_path(self, tmp_path, monkeypatch):
        path = tmp_path / "backend.log"
        _write_log(
            path,
            [
                _entry("ERROR", "10:00:00", "old"),
                _entry("ERROR", "10:00:03", "new"),
            ],
        )
        monkeypatch.setattr(logger_module, "LOG_FILE", path)
        result = logs_routes._read_recent_lines(
            10, _ERROR_LEVELS, since="10:00:01"
        )
        assert [e["ts"] for e in result] == ["10:00:03"]
