/**
 * LogConsole — shared presentational layer for the diagnostic-logs viewer.
 *
 * Renders three pieces:
 *   - Filter row     (level chips + Refresh + Pause/Resume live tail)
 *   - Console panel  (dark stone-900 panel with monospace LogRow entries)
 *   - Action row     (Clear / Copy / Download bundle)
 *
 * Both `LogsModal` and `LogsSection` compose these with their own outer
 * chrome. State and handlers come from `useLogsState`, so the two
 * surfaces stay in lockstep behaviorally — they only differ in framing
 * (Dialog vs settings page).
 *
 * Rendering note: we use a plain `<ul>{lines.map(...)}</ul>` rather
 * than virtualisation. The earlier react-window v2 attempt had a
 * first-paint window where dynamic row heights hadn't been measured
 * yet — for multi-line stack-trace / WARNING rows that showed up as
 * visible overlap. With the default fetch of 500 lines × ~6 DOM
 * nodes/row the total node count is well under what modern browsers
 * lay out in a frame, so the virtualisation wasn't earning its
 * keep. Plain rendering is rock-solid and the perf budget is fine.
 */
import React from 'react';
import {
  ArrowsClockwise,
  CircleNotch,
  Copy,
  DownloadSimple,
  Pause,
  Play,
  Trash,
  Warning,
  XCircle,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import type { LogLine } from '@/lib/api/logs';
import { LEVEL_FILTERS, type LevelFilter } from './useLogsState';

type ChipPalette = 'modal' | 'page';

interface LogConsoleProps {
  lines: LogLine[];
  filter: LevelFilter;
  onFilterChange: (next: LevelFilter) => void;
  loading: boolean;
  logFilePresent: boolean;
  confirmingClear: boolean;
  onRefresh: () => void;
  onCopy: () => void;
  onDownload: () => void;
  onClear: () => void;
  /** Whether to show the destructive Clear logs button. Admins only; default true. */
  canClear?: boolean;
  /** Live-tail polling status + toggle. Hook owns the actual interval. */
  paused?: boolean;
  onTogglePaused?: (next: boolean) => void;
  /**
   * Modal mode wraps its filters in a tinted-amber pressed state (matches
   * SharingModal's primary chip), page mode uses cream/amber that reads
   * better against the white settings background.
   */
  variant?: ChipPalette;
  /** Tailwind classes that bound the panel's vertical size. */
  panelMaxHeightClassName?: string;
}

export const LogConsole: React.FC<LogConsoleProps> = ({
  lines,
  filter,
  onFilterChange,
  loading,
  logFilePresent,
  confirmingClear,
  onRefresh,
  onCopy,
  onDownload,
  onClear,
  canClear = true,
  paused,
  onTogglePaused,
  variant = 'page',
  panelMaxHeightClassName = 'max-h-[58vh]',
}) => {
  return (
    <div className="space-y-4">
      <FilterRow
        filter={filter}
        onFilterChange={onFilterChange}
        loading={loading}
        onRefresh={onRefresh}
        paused={paused}
        onTogglePaused={onTogglePaused}
        variant={variant}
      />
      <ConsolePanel
        lines={lines}
        loading={loading}
        logFilePresent={logFilePresent}
        panelMaxHeightClassName={panelMaxHeightClassName}
      />
      <ActionRow
        onClear={onClear}
        onCopy={onCopy}
        onDownload={onDownload}
        loading={loading}
        hasLines={lines.length > 0}
        confirmingClear={confirmingClear}
        canClear={canClear}
      />
    </div>
  );
};

// ── Subcomponents ─────────────────────────────────────────────────

const FilterRow: React.FC<{
  filter: LevelFilter;
  onFilterChange: (next: LevelFilter) => void;
  loading: boolean;
  onRefresh: () => void;
  paused?: boolean;
  onTogglePaused?: (next: boolean) => void;
  variant: ChipPalette;
}> = ({ filter, onFilterChange, loading, onRefresh, paused, onTogglePaused, variant }) => (
  <div className="flex items-center gap-2 flex-wrap">
    {LEVEL_FILTERS.map((f) => {
      const isActive = filter === f.id;
      const activeClasses =
        variant === 'modal'
          ? 'border-primary/40 bg-primary/5 text-foreground'
          : 'border-amber-500/50 bg-amber-50 text-stone-900';
      const inactiveClasses =
        variant === 'modal'
          ? 'border-border/60 bg-background text-muted-foreground hover:text-foreground'
          : 'border-stone-200 bg-white text-stone-500 hover:text-stone-900';
      return (
        <button
          key={f.id}
          onClick={() => onFilterChange(f.id)}
          className={[
            'px-3 py-1 text-[11px] uppercase tracking-[0.08em] rounded-full border transition-colors',
            isActive ? activeClasses : inactiveClasses,
          ].join(' ')}
          aria-pressed={isActive}
        >
          {f.label}
        </button>
      );
    })}
    <div className="ml-auto flex items-center gap-1">
      {onTogglePaused && (
        <button
          onClick={() => onTogglePaused(!paused)}
          className={[
            'inline-flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-[0.08em] rounded-full',
            variant === 'modal'
              ? 'text-muted-foreground hover:text-foreground'
              : 'text-stone-500 hover:text-stone-900',
          ].join(' ')}
          title={paused ? 'Resume live tail (poll every 30 s)' : 'Pause live tail'}
          aria-pressed={!!paused}
        >
          {paused ? <Play size={12} weight="fill" /> : <Pause size={12} weight="fill" />}
          {paused ? 'Resume' : 'Live'}
        </button>
      )}
      <button
        onClick={onRefresh}
        className={[
          'inline-flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-[0.08em] rounded-full',
          variant === 'modal'
            ? 'text-muted-foreground hover:text-foreground'
            : 'text-stone-500 hover:text-stone-900',
        ].join(' ')}
        title="Refresh"
      >
        <ArrowsClockwise size={12} className={loading ? 'animate-spin' : ''} />
        Refresh
      </button>
    </div>
  </div>
);

const ConsolePanel: React.FC<{
  lines: LogLine[];
  loading: boolean;
  logFilePresent: boolean;
  panelMaxHeightClassName: string;
}> = ({ lines, loading, logFilePresent, panelMaxHeightClassName }) => {
  const showEmpty = !loading && lines.length === 0;
  const showLoading = loading && lines.length === 0;

  return (
    <div className="rounded-lg border border-stone-800/60 bg-stone-900 text-stone-100 font-mono text-[12px] leading-relaxed shadow-inner overflow-hidden">
      <div className={`${panelMaxHeightClassName} overflow-y-auto`}>
        {showLoading ? (
          <div className="h-48 flex items-center justify-center text-stone-400">
            <CircleNotch size={16} className="mr-2 animate-spin" />
            Loading logs…
          </div>
        ) : !logFilePresent ? (
          <EmptyState
            title="No log file on disk yet."
            body="The rotating handler creates the file on the first log line. Trigger any action and refresh."
          />
        ) : showEmpty ? (
          <EmptyState title="All quiet." body="No matching lines for this filter." />
        ) : (
          <ul className="divide-y divide-stone-800/80">
            {lines.map((line, i) => (
              <LogRow key={`${line.ts}-${i}`} line={line} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

const EmptyState: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <div className="h-48 flex flex-col items-center justify-center text-stone-400 px-6 text-center">
    <p className="text-stone-200">{title}</p>
    <p className="text-[11px] mt-1 max-w-sm">{body}</p>
  </div>
);

const ActionRow: React.FC<{
  onClear: () => void;
  onCopy: () => void;
  onDownload: () => void;
  loading: boolean;
  hasLines: boolean;
  confirmingClear: boolean;
  canClear: boolean;
}> = ({ onClear, onCopy, onDownload, loading, hasLines, confirmingClear, canClear }) => (
  <div className="flex items-center gap-2 flex-wrap">
    {canClear && (
      <Button
        variant="ghost"
        size="sm"
        onClick={onClear}
        disabled={loading}
        className={
          confirmingClear
            ? 'gap-2 text-rose-700 hover:text-rose-800'
            : 'gap-2 text-stone-500 hover:text-stone-900'
        }
      >
        <Trash size={14} />
        {confirmingClear ? 'Click again to clear' : 'Clear logs'}
      </Button>
    )}
    <Button
      variant="ghost"
      size="sm"
      onClick={onCopy}
      disabled={loading || !hasLines}
      className="gap-2 text-stone-500 hover:text-stone-900"
    >
      <Copy size={14} />
      Copy view
    </Button>
    <div className="flex-1" />
    <Button variant="default" size="sm" onClick={onDownload} className="gap-2">
      <DownloadSimple size={14} weight="bold" />
      Download bundle (.zip)
    </Button>
  </div>
);

const LogRow: React.FC<{ line: LogLine }> = ({ line }) => {
  const isError = line.level === 'ERROR' || line.level === 'CRITICAL';
  const isWarn = line.level === 'WARNING';
  return (
    <li className="px-4 py-2.5 hover:bg-stone-800/40 transition-colors">
      <div className="flex items-center gap-2 text-[11px] tracking-tight">
        <span className="text-stone-500 tabular-nums">{line.ts}</span>
        <span
          className={[
            'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm uppercase tracking-[0.06em] text-[10px] font-semibold',
            isError
              ? 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30'
              : isWarn
                ? 'bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30'
                : 'bg-stone-700/40 text-stone-400 ring-1 ring-stone-600/30',
          ].join(' ')}
        >
          {isError ? (
            <XCircle size={10} weight="fill" />
          ) : isWarn ? (
            <Warning size={10} weight="fill" />
          ) : null}
          {line.level}
        </span>
        <span className="text-stone-400 truncate" title={line.logger}>
          {line.logger}
        </span>
      </div>
      <pre className="mt-1 whitespace-pre-wrap break-words text-stone-100 text-[12px] leading-relaxed font-mono pl-[3px]">
        {line.message}
      </pre>
    </li>
  );
};
