/**
 * useLogsState — shared state + handlers for the diagnostic-logs viewer.
 *
 * Powers both `LogsModal` (chat-header dialog) and `LogsSection`
 * (settings tab). Centralizes the fetch lifecycle, level filter,
 * clipboard copy, bundle download, and clear-with-confirm flow so the
 * two surfaces are guaranteed to behave identically.
 *
 * The two callers differ only in chrome (Dialog vs settings page
 * layout) — every interaction is delegated here.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { logsAPI, type LogLine } from '@/lib/api/logs';
import { copyToClipboard } from '@/lib/clipboard';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';
import { getAdminMode } from '@/lib/adminMode';

const log = createLogger('logs-state');

export type LevelFilter = 'errors' | 'warnings' | 'all';

export const LEVEL_FILTERS: { id: LevelFilter; label: string }[] = [
  { id: 'errors', label: 'Errors' },
  { id: 'warnings', label: 'Errors + warnings' },
  { id: 'all', label: 'All levels' },
];

interface UseLogsStateOpts {
  /** When false (modal closed), the hook skips the initial fetch. */
  active?: boolean;
}

/**
 * How often to fetch new tail lines while the modal is open. 30 s
 * matches what an admin actually needs from a diagnostic surface —
 * fast enough that a freshly-produced error shows up in the same
 * support session, slow enough not to burn server cycles on a Logs
 * tab that's been left open.
 */
const LIVE_TAIL_INTERVAL_MS = 30_000;

/**
 * Pull a bigger window now that virtualisation makes row count free.
 * Gives operators enough scrollback for a real incident postmortem.
 */
const INITIAL_LOG_LINES = 500;

export function useLogsState({ active = true }: UseLogsStateOpts = {}) {
  // /logs/clear is admin-only on the backend (a non-admin's POST would
  // 403). Surface the same gate to the UI so the "Delete logs after
  // download" checkbox only renders for admins — non-admins still see
  // the confirmation dialog but without the destructive option.
  const canDeleteLogs = getAdminMode();
  const { toasts, dismissToast, success, error } = useToast();
  // ``rawLines`` is everything we've fetched (all levels). The visible
  // ``lines`` list is derived by applying ``filter`` client-side via
  // useMemo so toggling between Errors / Warnings / All never hits the
  // backend. Bumped to 500 entries; virtualisation handles the cost.
  const [rawLines, setRawLines] = useState<LogLine[]>([]);
  const [filter, setFilter] = useState<LevelFilter>('errors');
  const [loading, setLoading] = useState(false);
  const [logFilePresent, setLogFilePresent] = useState(true);
  const [confirmingClear, setConfirmingClear] = useState(false);
  // Whether the 30 s live-tail poll is running. Defaults to live; the
  // user can pause via the LogConsole control if they want a stable
  // snapshot to read.
  const [paused, setPaused] = useState(false);

  // Download-bundle confirmation dialog state. Lives in this hook (not
  // in LogsModal/LogsSection) so both surfaces share the same flow.
  const [downloadDialogOpen, setDownloadDialogOpen] = useState(false);
  const [deleteAfterDownload, setDeleteAfterDownload] = useState(false);
  // Snapshot of the persisted value so we only PUT when the user changed it.
  const persistedDeleteAfterDownload = useRef<boolean>(false);

  // Ref-mirror so the polling closure can read the freshest timestamp
  // without retriggering the interval setup. Plain state would force
  // the useEffect below to re-create the interval on every tick.
  const newestTsRef = useRef<string | null>(null);
  useEffect(() => {
    if (rawLines.length === 0) {
      newestTsRef.current = null;
      return;
    }
    newestTsRef.current = rawLines[rawLines.length - 1].ts;
  }, [rawLines]);

  // Initial / manual load — always full window, ``all`` level so the
  // client-side filter has everything to choose from.
  const loadLines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await logsAPI.getRecent(INITIAL_LOG_LINES, 'all');
      setRawLines(res.lines);
      setLogFilePresent(res.log_file_present);
    } catch (e) {
      log.error({ err: e }, 'failed to load logs');
      error('Could not load logs');
    } finally {
      setLoading(false);
    }
  }, [error]);

  // Refetch whenever the surface activates. The filter is now applied
  // client-side, so toggling chips does not trigger a refetch.
  useEffect(() => {
    if (!active) return;
    loadLines();
  }, [active, loadLines]);

  // Incremental tail fetch — pulls only lines newer than what we have.
  // No-op if rawLines is empty (we haven't done the initial load yet).
  const fetchSinceNewest = useCallback(async () => {
    const since = newestTsRef.current;
    if (!since) return;
    try {
      const res = await logsAPI.getRecent(INITIAL_LOG_LINES, 'all', { since });
      setLogFilePresent(res.log_file_present);
      if (!res.lines.length) return;
      setRawLines((prev) => {
        // Dedupe defensively: clock skew at a rotation boundary could
        // theoretically duplicate an entry. Key is (ts, message) which
        // is unique enough for human-readable log text.
        const seen = new Set(prev.map((l) => `${l.ts}${l.message}`));
        const fresh = res.lines.filter(
          (l) => !seen.has(`${l.ts}${l.message}`),
        );
        if (fresh.length === 0) return prev;
        const next = [...prev, ...fresh];
        // Cap memory at 4× the initial window. Old entries fall off the
        // front; user can still hit Refresh for a fresh server-side
        // window if they need history.
        const cap = INITIAL_LOG_LINES * 4;
        return next.length > cap ? next.slice(next.length - cap) : next;
      });
    } catch (e) {
      // Polling failures are best-effort — keep the existing data
      // visible and let the next tick try again. Toast only on the
      // explicit Refresh path.
      log.warn({ err: e }, 'live-tail poll failed');
    }
  }, []);

  // 30 s live-tail poll. Paused when the surface is closed, the user
  // explicitly toggled pause, or the tab is hidden (Page Visibility).
  //
  // We don't tear down + rebuild the interval on visibility changes;
  // instead the per-tick closure checks `document.hidden` and short-
  // circuits. That keeps the timer state machine simple and avoids
  // re-creating intervals on every Cmd-Tab. The catch-up fetch on
  // regaining focus is what gives the live tail its responsiveness
  // without firing real GETs while the tab is hidden.
  useEffect(() => {
    if (!active || paused) return;

    const tick = () => {
      if (typeof document !== 'undefined' && document.hidden) return;
      void fetchSinceNewest();
    };
    const id = window.setInterval(tick, LIVE_TAIL_INTERVAL_MS);
    const onVis = () => {
      if (!document.hidden) {
        // Catch-up immediately on regaining focus so the user doesn't
        // wait the full 30 s for the next tick.
        void fetchSinceNewest();
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [active, paused, fetchSinceNewest]);

  // Visible list: filter the raw stream by the current chip.
  const lines = useMemo(() => {
    if (filter === 'all') return rawLines;
    if (filter === 'warnings') {
      return rawLines.filter((l) =>
        l.level === 'WARNING' || l.level === 'ERROR' || l.level === 'CRITICAL',
      );
    }
    // 'errors'
    return rawLines.filter(
      (l) => l.level === 'ERROR' || l.level === 'CRITICAL',
    );
  }, [rawLines, filter]);

  // Load the user's "auto-delete on download" preference once the
  // surface activates so the checkbox is pre-set the first time the
  // download dialog opens. Skipped for non-admins: they can't delete
  // logs so the preference would be inert and the GET is wasted work.
  useEffect(() => {
    if (!active || !canDeleteLogs) return;
    let cancelled = false;
    (async () => {
      try {
        const prefs = await logsAPI.getPreferences();
        if (cancelled) return;
        persistedDeleteAfterDownload.current = prefs.auto_delete_on_download;
        setDeleteAfterDownload(prefs.auto_delete_on_download);
      } catch (e) {
        // Non-fatal — checkbox just stays unchecked.
        log.warn({ err: e }, 'failed to load log preferences');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active, canDeleteLogs]);

  const formatLines = useMemo(
    () =>
      lines
        .map((l) => `${l.ts} [${l.level}] ${l.logger}: ${l.message}`)
        .join('\n'),
    [lines],
  );

  const handleCopy = useCallback(async () => {
    if (!lines.length) {
      error('Nothing to copy yet');
      return;
    }
    const ok = await copyToClipboard(formatLines);
    if (ok) success(`Copied ${lines.length} lines`);
    else error('Could not copy. Select the text manually.');
  }, [lines, formatLines, success, error]);

  /**
   * Open the download confirmation dialog instead of starting the
   * download immediately. The actual download + (optional) clear runs in
   * `confirmDownload` once the user clicks the dialog's Download button.
   */
  const handleDownload = useCallback(() => {
    setDownloadDialogOpen(true);
  }, []);

  const confirmDownload = useCallback(async () => {
    setDownloadDialogOpen(false);

    // Start the browser download via anchor (JWT in the query string).
    const a = document.createElement('a');
    a.href = logsAPI.bundleUrl();
    a.rel = 'noopener';
    a.click();

    // Persist the checkbox state if it changed. Fire-and-forget — a
    // preference write failure shouldn't block the bundle download.
    // Skipped for non-admins since they can't act on the preference
    // anyway (and the backend write succeeds but is then unused).
    if (canDeleteLogs && deleteAfterDownload !== persistedDeleteAfterDownload.current) {
      logsAPI
        .setPreferences({ auto_delete_on_download: deleteAfterDownload })
        .then(() => {
          persistedDeleteAfterDownload.current = deleteAfterDownload;
        })
        .catch((e) => {
          log.warn({ err: e }, 'failed to persist log preference');
        });
    }

    // If the user opted in, wait briefly so the browser has time to
    // begin streaming the ZIP, then clear the server-side logs. The
    // canDeleteLogs guard is defense-in-depth — the checkbox is hidden
    // for non-admins so deleteAfterDownload should already be false.
    if (canDeleteLogs && deleteAfterDownload) {
      window.setTimeout(async () => {
        try {
          await logsAPI.clear();
          success('Logs cleared from server');
          await loadLines();
        } catch (e) {
          log.error({ err: e }, 'failed to clear logs after download');
          error('Could not clear logs after download');
        }
      }, 1500);
    }
  }, [canDeleteLogs, deleteAfterDownload, loadLines, success, error]);

  const handleClear = useCallback(async () => {
    if (!confirmingClear) {
      setConfirmingClear(true);
      // Reset the confirm state if the user walks away.
      setTimeout(() => setConfirmingClear(false), 4000);
      return;
    }
    setConfirmingClear(false);
    setLoading(true);
    try {
      await logsAPI.clear();
      success('Logs cleared');
      await loadLines();
    } catch (e) {
      log.error({ err: e }, 'failed to clear logs');
      error('Could not clear logs');
    } finally {
      setLoading(false);
    }
  }, [confirmingClear, loadLines, success, error]);

  return {
    lines,
    filter,
    setFilter,
    loading,
    logFilePresent,
    confirmingClear,
    loadLines,
    handleCopy,
    handleDownload,
    handleClear,
    // Live-tail control.
    paused,
    setPaused,
    // Download confirmation dialog state.
    downloadDialogOpen,
    setDownloadDialogOpen,
    deleteAfterDownload,
    setDeleteAfterDownload,
    confirmDownload,
    canDeleteLogs,
    // Toast plumbing — the consumer mounts <ToastContainer /> with these.
    toasts,
    dismissToast,
  };
}
