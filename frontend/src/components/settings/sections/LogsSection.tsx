/**
 * LogsSection — settings-page variant of the diagnostic logs viewer.
 *
 * Same console aesthetic as `LogsModal` but reflows for the settings
 * content area: full-width panel, no Dialog chrome, prose-style intro
 * paragraph that explains what the bundle contains so the admin knows
 * what they're sharing.
 *
 * Behavior + content all come from `useLogsState` and `LogConsole` so
 * the modal and this section can never drift out of sync. This file
 * additionally hosts the admin-only "Auto-clear logs weekly" toggle
 * since the housekeeping setting is global, not per-user.
 */
import React, { useEffect, useState } from 'react';
import { LogConsole } from '@/components/project/LogConsole';
import { useLogsState } from '@/components/project/useLogsState';
import { DownloadLogsConfirmDialog } from '@/components/project/DownloadLogsConfirmDialog';
import { logsAPI, type LogHousekeeping } from '@/lib/api/logs';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';
import { getAdminMode } from '@/lib/adminMode';

const log = createLogger('logs-section');

const LogHousekeepingCard: React.FC = () => {
  const { success, error } = useToast();
  const [config, setConfig] = useState<LogHousekeeping | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await logsAPI.getHousekeeping();
        if (!cancelled) setConfig(res);
      } catch (e) {
        log.warn({ err: e }, 'failed to load housekeeping config');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleToggle = async (next: boolean) => {
    if (!config) return;
    setSaving(true);
    try {
      const updated = await logsAPI.setHousekeeping({ weekly_clear_enabled: next });
      setConfig(updated);
      success(next ? 'Weekly log auto-clear enabled' : 'Weekly log auto-clear disabled');
    } catch (e) {
      log.error({ err: e }, 'failed to update housekeeping');
      // 409 from the backend means the scheduler bumped last_run_at between
      // our read and write. Re-fetch so the Switch snaps back to the real
      // server state instead of lingering on the value the user attempted.
      try {
        const latest = await logsAPI.getHousekeeping();
        setConfig(latest);
      } catch (refreshErr) {
        log.warn({ err: refreshErr }, 'failed to re-fetch housekeeping after error');
      }
      error('Could not update log housekeeping setting');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-md border border-stone-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-medium text-stone-900">
            Auto-clear logs weekly
          </h3>
          <p className="mt-1 text-xs text-stone-600 max-w-prose">
            Truncates the rotating <code>backend.log</code> files and removes
            archives once every 7 days so the deployment doesn&apos;t accrue
            stale diagnostics indefinitely.
          </p>
          {config?.last_run_at && (
            <p className="mt-2 text-xs text-stone-500">
              Last cleared automatically: {new Date(config.last_run_at).toLocaleString()}
            </p>
          )}
        </div>
        <Switch
          // PUT /logs/housekeeping is admin-only — disable for non-admins
          // so they can still see the card's last-cleared timestamp without
          // clicking into a confusing 403.
          checked={config?.weekly_clear_enabled ?? false}
          disabled={!config || saving || !getAdminMode()}
          onCheckedChange={handleToggle}
        />
      </div>
    </div>
  );
};

export const LogsSection: React.FC = () => {
  const state = useLogsState({ active: true });

  return (
    <div className="max-w-5xl space-y-6 pb-8">
      <header>
        <h2 className="text-lg font-semibold text-stone-900">Diagnostic logs</h2>
        <p className="mt-1 text-sm text-stone-600 max-w-prose leading-relaxed">
          Recent backend and frontend errors from this deployment. Download the{' '}
          <strong>support bundle</strong> to share a complete snapshot — the ZIP
          includes the rotating log files (with secrets scrubbed), env-var
          names, applied migrations, and deployment metadata.
        </p>
      </header>

      <LogHousekeepingCard />

      <LogConsole
        variant="page"
        panelMaxHeightClassName="max-h-[58vh]"
        lines={state.lines}
        filter={state.filter}
        onFilterChange={state.setFilter}
        loading={state.loading}
        logFilePresent={state.logFilePresent}
        confirmingClear={state.confirmingClear}
        onRefresh={state.loadLines}
        onCopy={state.handleCopy}
        onDownload={state.handleDownload}
        onClear={state.handleClear}
        paused={state.paused}
        onTogglePaused={state.setPaused}
      />

      <DownloadLogsConfirmDialog
        open={state.downloadDialogOpen}
        onOpenChange={state.setDownloadDialogOpen}
        deleteAfterDownload={state.deleteAfterDownload}
        onDeleteAfterDownloadChange={state.setDeleteAfterDownload}
        onConfirm={state.confirmDownload}
        canDelete={state.canDeleteLogs}
      />
    </div>
  );
};
