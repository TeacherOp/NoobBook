/**
 * SavedInsightsSection — auto-refreshing chat prompts in the Studio panel.
 *
 * A saved insight is a user prompt that the backend re-runs daily or
 * weekly. This section lists them with their latest result and lets the
 * user trigger a manual refresh or delete one. Creation happens from the
 * chat surface (the "Save as insight" button on user messages); this
 * section is read-and-manage only.
 *
 * Hidden when there are no saved insights so we don't add empty noise
 * to the Studio panel.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowsClockwise,
  CircleNotch,
  Lightbulb,
  Trash,
  Warning,
} from '@phosphor-icons/react';
import { useStudioContext } from '../studio-hooks';
import {
  insightsAPI,
  type SavedInsight,
  type InsightCadence,
} from '@/lib/api/insights';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('saved-insights-section');

const POLL_INTERVAL_MS = 15_000;

const cadenceLabel = (c: InsightCadence) => (c === 'daily' ? 'Daily' : 'Weekly');

const formatLastRun = (iso: string | null): string => {
  if (!iso) return 'Not run yet';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Not run yet';
  const diffMs = Date.now() - d.getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
};

export const SavedInsightsSection: React.FC = () => {
  const { projectId } = useStudioContext();
  const { success, error } = useToast();

  const [insights, setInsights] = useState<SavedInsight[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SavedInsight | null>(null);

  const loadInsights = useCallback(async () => {
    try {
      const rows = await insightsAPI.list(projectId);
      setInsights(rows);
    } catch (err) {
      log.error({ err }, 'failed to load insights');
    } finally {
      setLoaded(true);
    }
  }, [projectId]);

  useEffect(() => {
    loadInsights();
  }, [loadInsights]);

  // Poll while any insight is currently running so the user sees the new
  // result land without a manual reload. Stops when no row is running.
  useEffect(() => {
    if (!insights.some((i) => i.is_running)) return;
    const interval = setInterval(loadInsights, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [insights, loadInsights]);

  const handleRefresh = useCallback(
    async (insight: SavedInsight) => {
      const ok = await insightsAPI.refresh(projectId, insight.id);
      if (ok) {
        // Optimistically flip is_running so the spinner shows; the next
        // poll picks up the canonical state from the backend.
        setInsights((prev) =>
          prev.map((row) => (row.id === insight.id ? { ...row, is_running: true } : row)),
        );
        success('Refresh started');
      } else {
        error('Could not start refresh');
      }
    },
    [projectId, success, error],
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDelete) return;
    const insight = pendingDelete;
    setPendingDelete(null);
    const ok = await insightsAPI.remove(projectId, insight.id);
    if (ok) {
      setInsights((prev) => prev.filter((row) => row.id !== insight.id));
      success('Insight deleted');
    } else {
      error('Could not delete insight');
    }
  }, [pendingDelete, projectId, success, error]);

  if (!loaded || insights.length === 0) {
    return null;
  }

  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <Lightbulb size={16} weight="bold" className="text-amber-600" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-700">
          Saved Insights
        </h3>
      </div>

      <div className="space-y-2">
        {insights.map((insight) => {
          const isExpanded = expandedId === insight.id;
          return (
            <div
              key={insight.id}
              className="rounded-lg border border-stone-200 bg-white p-3 text-sm"
            >
              <div className="flex items-start gap-2">
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : insight.id)}
                  className="flex-1 min-w-0 text-left"
                >
                  <div className="font-medium text-stone-800 truncate">
                    {insight.title}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {cadenceLabel(insight.cadence)} · {formatLastRun(insight.last_run_at)}
                    {insight.last_error && (
                      <span className="ml-2 inline-flex items-center gap-1 text-destructive">
                        <Warning size={12} weight="bold" />
                        last refresh failed
                      </span>
                    )}
                  </div>
                </button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRefresh(insight)}
                  disabled={insight.is_running}
                  title="Refresh now"
                  className="h-7 w-7 p-0"
                >
                  {insight.is_running ? (
                    <CircleNotch size={14} className="animate-spin" />
                  ) : (
                    <ArrowsClockwise size={14} />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPendingDelete(insight)}
                  title="Delete insight"
                  className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                >
                  <Trash size={14} />
                </Button>
              </div>

              {isExpanded && (
                <div className="mt-3 space-y-2 border-t border-stone-100 pt-2">
                  <div>
                    <div className="text-xs font-medium text-stone-500">Prompt</div>
                    <p className="mt-0.5 text-xs text-stone-700 whitespace-pre-wrap">
                      {insight.prompt}
                    </p>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-stone-500">
                      {insight.last_error ? 'Last error' : 'Last result'}
                    </div>
                    <p className="mt-0.5 text-xs text-stone-700 whitespace-pre-wrap">
                      {insight.last_error
                        ? insight.last_error
                        : insight.last_result || 'No result yet — refresh to populate.'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <AlertDialog open={!!pendingDelete} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete saved insight?</AlertDialogTitle>
            <AlertDialogDescription>
              This stops the scheduled refresh and removes the stored result.
              The chats that were already run stay intact.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
};
