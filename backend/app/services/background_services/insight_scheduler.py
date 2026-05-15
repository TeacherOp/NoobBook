"""
Saved-Insight Scheduler — daemon thread that periodically refreshes any
insight whose cadence interval has elapsed.

Design:
- One daemon thread per process. We run a single gunicorn worker in prod
  (and a Flask dev server in dev), so a single in-process scheduler is
  sufficient — no cross-process coordination needed.
- Tick interval is intentionally coarse (5 minutes). Cadences are daily
  or weekly; sub-minute precision isn't needed and the looser interval
  keeps Supabase chatter low.
- Per-insight refreshes are submitted to a small ThreadPoolExecutor so a
  slow refresh (long agentic loop) doesn't block the next tick from
  enqueuing other due insights.
- The atomic claim in insight_service.refresh_insight makes this safe
  against the manual /refresh route racing the scheduler.
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.services.data_services.insight_service import insight_service

logger = logging.getLogger(__name__)


TICK_INTERVAL_SECONDS = 300  # 5 min
MAX_CONCURRENT_REFRESHES = 4
STARTUP_DELAY_SECONDS = 30   # let the app finish booting before first tick


class InsightScheduler:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._executor = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_REFRESHES,
            thread_name_prefix="insight-refresh",
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._run,
            name="insight-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("Insight scheduler started (tick=%ss)", TICK_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        # Sleep briefly before the first tick so we don't compete with app
        # warmup for resources.
        if self._stop.wait(STARTUP_DELAY_SECONDS):
            return

        # Clear any `is_running=true` rows abandoned by a previous worker
        # that was SIGKILLed mid-refresh (Coolify redeploy, OOM, watchdog
        # bounce). Without this, the affected insight would be skipped
        # forever because `claim_for_refresh` filters on `is_running=false`.
        try:
            insight_service.reset_stale_claims()
        except Exception as exc:
            logger.warning("Stale-claim sweep failed: %s", exc)

        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.exception("Insight scheduler tick failed: %s", exc)
            if self._stop.wait(TICK_INTERVAL_SECONDS):
                break

    def _tick(self) -> None:
        due = insight_service.find_due_insights()
        if not due:
            return
        logger.info("Insight scheduler: %d due", len(due))
        for row in due:
            insight_id = row["id"]
            if not insight_service.claim_for_refresh(insight_id):
                # Lost the race with manual refresh or a prior tick.
                continue
            self._executor.submit(self._refresh_safely, insight_id)

    @staticmethod
    def _refresh_safely(insight_id: str) -> None:
        try:
            insight_service.refresh_insight(insight_id)
        except Exception as exc:
            logger.exception("Insight refresh %s threw: %s", insight_id, exc)


insight_scheduler = InsightScheduler()
