/**
 * Logs API — admin diagnostic bundle + client-side error reporting.
 *
 * The admin endpoints (recent / bundle / clear) are gated by @require_admin
 * on the backend. The client-error endpoint accepts any authenticated user
 * so the frontend's window.onerror hook can report from any session.
 */
import { api, API_HOST, getAuthUrl } from './client';

export interface LogLine {
  ts: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  logger: string;
  message: string;
}

export interface RecentLogsResponse {
  success: boolean;
  lines: LogLine[];
  log_file_present: boolean;
}

export interface ClientErrorPayload {
  message: string;
  stack?: string;
  url?: string;
  userAgent?: string;
  timestamp?: string;
}

export interface LogPreferences {
  auto_delete_on_download: boolean;
}

export interface LogHousekeeping {
  weekly_clear_enabled: boolean;
  last_run_at: string | null;
}

export const logsAPI = {
  /**
   * Fetch recent log lines.
   *
   * ``since`` is an optional "HH:MM:SS" prefix — pass the newest
   * timestamp the client already holds to make the backend return
   * just the lines that landed after it. This is what the live-tail
   * poll uses so each 30 s tick reads at most a few KB.
   */
  async getRecent(
    n = 100,
    level: 'errors' | 'warnings' | 'all' = 'errors',
    opts: { since?: string } = {},
  ) {
    const params: Record<string, string | number> = { n, level };
    if (opts.since) params.since = opts.since;
    const res = await api.get<RecentLogsResponse>('/logs/recent', { params });
    return res.data;
  },

  /** Browser-direct download URL for the support bundle. JWT goes in query
   * string because <a download> can't set Authorization headers. */
  bundleUrl(): string {
    return getAuthUrl(`${API_HOST}/api/v1/logs/bundle`);
  },

  async clear() {
    const res = await api.post<{ success: boolean; cleared: number }>('/logs/clear');
    return res.data;
  },

  /** Per-user "auto-delete logs after download" preference. */
  async getPreferences(): Promise<LogPreferences> {
    const res = await api.get<{ success: boolean } & LogPreferences>('/logs/preferences');
    return { auto_delete_on_download: !!res.data.auto_delete_on_download };
  },

  async setPreferences(prefs: LogPreferences): Promise<LogPreferences> {
    const res = await api.put<{ success: boolean } & LogPreferences>('/logs/preferences', prefs);
    return { auto_delete_on_download: !!res.data.auto_delete_on_download };
  },

  /** Global weekly auto-clear configuration (read is open; write is admin-only). */
  async getHousekeeping(): Promise<LogHousekeeping> {
    const res = await api.get<{ success: boolean } & LogHousekeeping>('/logs/housekeeping');
    return {
      weekly_clear_enabled: !!res.data.weekly_clear_enabled,
      last_run_at: res.data.last_run_at ?? null,
    };
  },

  async setHousekeeping(prefs: { weekly_clear_enabled: boolean }): Promise<LogHousekeeping> {
    const res = await api.put<{ success: boolean } & LogHousekeeping>('/logs/housekeeping', prefs);
    return {
      weekly_clear_enabled: !!res.data.weekly_clear_enabled,
      last_run_at: res.data.last_run_at ?? null,
    };
  },

  /** Fire-and-forget client error report. We don't await the response in
   * the error handler — keeping the post lightweight + non-blocking is the
   * point. */
  async reportClientError(payload: ClientErrorPayload): Promise<void> {
    try {
      await api.post('/logs/client', payload);
    } catch {
      // Swallow — reporting an error must never throw an error itself.
    }
  },
};
