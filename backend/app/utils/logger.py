"""
Logging configuration for NoobBook backend.

Sets up structured logging with consistent format across all modules.
Usage: import logging; logger = logging.getLogger(__name__)
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# Public path constants — used by `app/api/logs/` to read/clear/bundle the log
# file without re-deriving the location.
LOG_DIR: Path | None = None
LOG_FILE: Path | None = None


class _RequestIdFilter(logging.Filter):
    """Inject the current request's correlation ID onto every LogRecord.

    Why: without this, a frontend bug report ("logged out at 14:32") has no
    way to find the corresponding backend log line. The req_id is set by the
    before_request hook in `app/api/__init__.py`. For records emitted outside
    Flask request context (startup, background ThreadPoolExecutor workers,
    CLI helpers) the placeholder "-" is used so the format string still
    renders cleanly.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "req_id"):
            # Lazy import — logger.py must stay importable without Flask
            # (some test paths and CLI helpers touch this before app init).
            from app.utils.request_context import get_request_id
            record.req_id = get_request_id()
        return True


def setup_logging(log_level: str = "DEBUG") -> None:
    """
    Configure the root logger with a human-readable format.

    Two handlers are attached to the root logger:
      - StreamHandler(stdout) — keeps `docker logs` working as before.
      - RotatingFileHandler(<DATA_DIR>/logs/backend.log) — persists logs to
        the `backend-data` volume so the admin "Logs" UI can serve them
        even after a container restart. 5MB × 5 archives = ~25MB ceiling.

    Called once at app startup in create_app(). All modules that use
    logging.getLogger(__name__) inherit this configuration.
    """
    global LOG_DIR, LOG_FILE

    level = getattr(logging, log_level.upper(), logging.DEBUG)

    # The `[req:%(req_id)s]` segment is what makes frontend-↔-backend
    # correlation possible. The matching parser at
    # `app/api/logs/routes.py:_LINE_RE` accepts both the new and the old
    # shape so already-rotated archives still display in the admin UI.
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [req:%(req_id)s]: %(message)s",
        datefmt="%H:%M:%S",
    )

    req_id_filter = _RequestIdFilter()

    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(req_id_filter)
    handlers.append(stream_handler)

    # File handler. Imported lazily so logger.py stays importable without
    # the Flask app being constructed (some test paths and CLI helpers
    # touch this module before config is available).
    try:
        from config import Config

        LOG_DIR = Path(Config.DATA_DIR) / "logs"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE = LOG_DIR / "backend.log"

        # Cap at 2 MB / 5 archives (10 MB total). The previous 5 MB cap
        # produced files large enough that the legacy whole-file logs
        # reader took 200 ms+ on slower Docker mounts. The admin UI now
        # uses a backward-block tail reader, so per-file size matters
        # less for read latency — but smaller archives also keep the
        # support bundle download snappy.
        file_handler = RotatingFileHandler(
            str(LOG_FILE),
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(req_id_filter)
        handlers.append(file_handler)
    except Exception as exc:  # noqa: BLE001 — file handler is best-effort
        # Don't crash startup if the volume isn't writable — stdout still
        # works and the admin Logs UI will simply show "no log file".
        sys.stderr.write(f"[logger] file handler disabled: {exc}\n")

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on reloads
    root.handlers = handlers

    # Quiet noisy third-party loggers
    for name in ("urllib3", "werkzeug", "httpcore", "httpx", "hpack", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)
