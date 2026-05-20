/**
 * SourceItem Component
 * Educational Note: Displays a single source with icon, name, size, and action menu.
 * Shows processing status with loading indicator for sources being processed.
 * Shows error indicator for sources that failed processing.
 * Uses a 3-dot dropdown menu for actions (rename, download, delete).
 */

import React, { useState } from 'react';
import {
  FileText,
  FilePdf,
  FileDoc,
  FilePpt,
  FileCsv,
  FileHtml,
  FilePng,
  FileJpg,
  FileXls,
  MarkdownLogo,
  File,
  MusicNote,
  Image,
  Table,
  Trash,
  DownloadSimple,
  Link,
  YoutubeLogo,
  CircleNotch,
  Warning,
  CheckCircle,
  DotsThreeVertical,
  PencilSimple,
  Stop,
  ArrowsClockwise,
  CloudArrowDown,
  Plug,
  NotionLogo,
} from '@phosphor-icons/react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { formatFileSize, isSourceViewable, type Source } from '../../lib/api/sources';

interface SourceItemProps {
  source: Source;
  onDownload: (sourceId: string) => void;
  onDelete: (sourceId: string, sourceName: string) => void;
  onRename: (sourceId: string, currentName: string) => void;
  onToggleActive: (sourceId: string, active: boolean) => void;
  onCancelProcessing: (sourceId: string) => void;
  onRetryProcessing: (sourceId: string) => void;
  onViewProcessed: (sourceId: string) => void;
  onSyncFreshdesk?: (sourceId: string) => void;
  onBackfillFreshdesk?: (sourceId: string) => void;
}

/**
 * Get the appropriate icon component for a source.
 * Educational Note: We extract the file extension from source.name first because it persists
 * across all status transitions. The embedding_info.file_extension gets overwritten when
 * processing completes (replaced with embedding stats), so it's only reliable for fresh uploads.
 * The backend `type` field uses "DOCUMENT" for all document types (PDF, DOCX, PPTX, TXT),
 * so it can't distinguish between them — but it's useful for non-file sources (URLs, text).
 */
const getSourceIcon = (source: Source): { icon: typeof File; weight?: 'bold' } => {
  // 1. Extract extension from source name (most reliable — persists across processing)
  const name = source.name || '';
  const lastDot = name.lastIndexOf('.');
  const nameExtension = lastDot > 0 ? name.substring(lastDot).toLowerCase() : '';

  // 2. Also check embedding_info (available on fresh uploads before processing overwrites it)
  const embeddingExtension = ((source.embedding_info as Record<string, string>)?.file_extension || '').toLowerCase();

  const fileExtension = nameExtension || embeddingExtension;

  // Map extension to icon (all bold for visual consistency)
  switch (fileExtension) {
    case '.pdf': return { icon: FilePdf, weight: 'bold' };
    case '.docx': return { icon: FileDoc, weight: 'bold' };
    case '.pptx': return { icon: FilePpt, weight: 'bold' };
    case '.txt': return { icon: FileText, weight: 'bold' };
    case '.csv': return { icon: FileCsv, weight: 'bold' };
    case '.xlsx': return { icon: FileXls, weight: 'bold' };
    case '.database': return { icon: Table, weight: 'bold' };
    case '.mcp': return { icon: Plug, weight: 'bold' };
    case '.notion': return { icon: NotionLogo, weight: 'bold' };
    case '.md': return { icon: MarkdownLogo, weight: 'bold' };
    case '.html': return { icon: FileHtml, weight: 'bold' };
    case '.json': case '.xml': return { icon: FileText, weight: 'bold' };
    case '.mp3': case '.wav': case '.m4a': case '.aac': case '.flac': return { icon: MusicNote, weight: 'bold' };
    case '.jpg': case '.jpeg': return { icon: FileJpg, weight: 'bold' };
    case '.png': return { icon: FilePng, weight: 'bold' };
    case '.gif': case '.webp': return { icon: Image, weight: 'bold' };
  }

  // 3. Fall back to backend `type` field (for URLs, pasted text, etc. that have no extension in name)
  const sourceType = source.type || '';
  switch (sourceType) {
    case 'YOUTUBE': return { icon: YoutubeLogo, weight: 'bold' };
    case 'LINK': case 'RESEARCH': return { icon: Link, weight: 'bold' };
    case 'TEXT': return { icon: FileText, weight: 'bold' };
    case 'AUDIO': return { icon: MusicNote, weight: 'bold' };
    case 'IMAGE': return { icon: Image, weight: 'bold' };
    case 'DATA': return { icon: Table, weight: 'bold' };
    case 'DATABASE': return { icon: Table, weight: 'bold' };
    case 'MCP': return { icon: Plug, weight: 'bold' };
    case 'NOTION': return { icon: NotionLogo, weight: 'bold' };
    case 'DOCUMENT': return { icon: FileText, weight: 'bold' };
    default: return { icon: File, weight: 'bold' };
  }
};

/**
 * Get a human-readable error message from processing_info.
 * Educational Note: The backend stores detailed error info in processing_info.error.
 * We extract a short, user-friendly message from it to show in the UI.
 */
const getErrorMessage = (source: Source): string => {
  const error = (source.processing_info as Record<string, string>)?.error || '';

  // YouTube IP blocking (common on cloud servers like AWS/GCP/Azure)
  if (error.toLowerCase().includes('requestblocked') || (error.toLowerCase().includes('ip') && error.toLowerCase().includes('cloud'))) {
    return 'YouTube blocks cloud server IPs (AWS/GCP/Azure). Works when self-hosted locally.';
  }
  if (error.toLowerCase().includes('no transcript') || error.toLowerCase().includes('disabled')) {
    return 'No transcript available for this video.';
  }
  if (error.toLowerCase().includes('unavailable') || error.toLowerCase().includes('private')) {
    return 'Video is unavailable (private, deleted, or region-locked).';
  }
  if (error.toLowerCase().includes('api key')) {
    return 'API key is invalid or expired. Check your settings.';
  }

  // Return the raw error if short enough, otherwise truncate
  if (error && error.length <= 100) return error;
  if (error) return error.substring(0, 100) + '...';
  return 'Processing failed';
};

/**
 * Get status display info (icon, color, text)
 * Educational Note: Different statuses indicate processing state:
 * - uploaded: Waiting to be processed (could be fresh upload or cancelled)
 * - processing: Currently extracting text from PDF
 * - embedding: Creating vector embeddings for semantic search
 * - ready: Successfully processed, available for chat
 * - error: Processing failed completely (no partial states - clean failure)
 */
const getStatusDisplay = (status: Source['status'], source?: Source) => {
  switch (status) {
    case 'uploaded':
      // Uploaded but not yet processing - could be cancelled or waiting
      return {
        icon: ArrowsClockwise,
        color: 'text-muted-foreground',
        animate: false,
        tooltip: 'Ready to process',
      };
    case 'processing':
      return {
        icon: CircleNotch,
        color: 'text-primary',
        animate: true,
        tooltip: 'Processing...',
      };
    case 'embedding':
      // Creating embeddings for semantic search
      return {
        icon: CircleNotch,
        color: 'text-blue-500',
        animate: true,
        tooltip: 'Embedding...',
      };
    case 'ready':
      return {
        icon: CheckCircle,
        color: 'text-green-600',
        animate: false,
        tooltip: 'Ready',
      };
    case 'error':
      return {
        icon: Warning,
        color: 'text-destructive',
        animate: false,
        tooltip: source ? getErrorMessage(source) : 'Processing failed',
      };
    default:
      return null;
  }
};

/**
 * SourceStageChip — small editorial pill showing the AI's current pass over
 * a source. Reuses the `reading-breathe` keyframe from the chat surface so
 * the visual language stays coherent across the app.
 */
const SourceStageChip: React.FC<{ status: Source['status'] }> = ({ status }) => {
  if (status === 'ready') return null;

  const config: Record<string, { label: string; classes: string; pulse: boolean }> = {
    uploaded: {
      label: 'Queued',
      classes: 'border-stone-200 bg-stone-50 text-stone-600',
      pulse: false,
    },
    processing: {
      label: 'Reading',
      classes: 'border-amber-200 bg-amber-50 text-amber-800',
      pulse: true,
    },
    embedding: {
      label: 'Indexing',
      classes: 'border-sky-200 bg-sky-50 text-sky-700',
      pulse: true,
    },
    error: {
      label: 'Failed',
      classes: 'border-rose-200 bg-rose-50 text-rose-700',
      pulse: false,
    },
  };

  const c = config[status];
  if (!c) return null;

  return (
    <span
      className={`inline-flex flex-shrink-0 items-center gap-1 rounded-full border px-1.5 py-0 text-[10px] font-medium leading-[14px] ${c.classes}`}
      style={c.pulse ? { animation: 'reading-breathe 2.4s ease-in-out infinite' } : undefined}
    >
      {c.label}
    </span>
  );
};

export const SourceItem: React.FC<SourceItemProps> = ({
  source,
  onDownload,
  onDelete,
  onRename,
  onToggleActive,
  onCancelProcessing,
  onRetryProcessing,
  onViewProcessed,
  onSyncFreshdesk,
  onBackfillFreshdesk,
}) => {
  const { icon: Icon, weight: iconWeight } = getSourceIcon(source);
  const statusDisplay = getStatusDisplay(source.status, source);
  const isFreshdesk = ((source.embedding_info as Record<string, string>)?.file_extension || '') === '.freshdesk';
  const isSyncing = isFreshdesk && (
    source.status === 'processing' ||
    !!(source.processing_info as Record<string, unknown>)?.syncing
  );
  const [backfillDialogOpen, setBackfillDialogOpen] = useState(false);
  // "processing" or "embedding" are actively working - show spinner and allow cancel
  const isProcessing = source.status === 'processing';
  const isEmbedding = source.status === 'embedding';
  const isActivelyWorking = isProcessing || isEmbedding;
  // "uploaded" status means source is waiting for processing (fresh upload or cancelled)
  const isWaitingToProcess = source.status === 'uploaded';
  // Source can be toggled active/inactive only when it's ready
  // Educational Note: No partial status - sources are either fully ready or failed
  const canToggleActive = source.status === 'ready';
  // Check if source can be viewed (ready + viewable type)
  const canView = isSourceViewable(source);

  /**
   * Handle click on the source row to view processed content
   * Educational Note: Only viewable sources (text-based, ready status) can be clicked.
   * We check the target to avoid triggering when clicking on interactive elements.
   */
  const handleRowClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // Don't trigger if clicking on interactive elements (handled by stopPropagation)
    // This is a fallback check
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.closest('[role="checkbox"]')) {
      return;
    }

    if (canView) {
      onViewProcessed(source.id);
    }
  };

  return (
    <>
    <div
      onClick={handleRowClick}
      className={`grid grid-cols-[auto_1fr_auto_auto] items-center gap-2 p-2 rounded-lg hover:bg-accent group transition-colors ${
        isActivelyWorking ? 'opacity-90' : ''
      } ${canView ? 'cursor-pointer' : ''}`}
    >
      {/* Icon Area - Shows category icon, transforms to menu on hover */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded transition-colors">
            {/* Category icon - visible by default, hidden on hover */}
            <Icon
              size={18}
              weight={iconWeight}
              className="text-muted-foreground group-hover:hidden"
            />
            {/* Menu icon - hidden by default, visible on hover */}
            <DotsThreeVertical
              size={18}
              weight="bold"
              className="text-muted-foreground hidden group-hover:block"
            />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" onClick={(e) => e.stopPropagation()}>
          {/* Retry/Start option - for error or uploaded (waiting) state */}
          {(source.status === 'error' || isWaitingToProcess) && (
            <DropdownMenuItem onClick={() => onRetryProcessing(source.id)}>
              <ArrowsClockwise size={14} className="mr-2" />
              {isWaitingToProcess ? 'Start Processing' : 'Retry Processing'}
            </DropdownMenuItem>
          )}

          {/* Stop option - only for actively working state (processing or embedding) */}
          {isActivelyWorking && (
            <DropdownMenuItem onClick={() => onCancelProcessing(source.id)}>
              <Stop size={14} className="mr-2" />
              {isEmbedding ? 'Stop Embedding' : 'Stop Processing'}
            </DropdownMenuItem>
          )}

          {/* Rename option - disabled during active work */}
          <DropdownMenuItem
            onClick={() => onRename(source.id, source.name)}
            disabled={isActivelyWorking}
          >
            <PencilSimple size={14} className="mr-2" />
            Rename
          </DropdownMenuItem>

          {/* Download option - disabled during active work */}
          <DropdownMenuItem
            onClick={() => onDownload(source.id)}
            disabled={isActivelyWorking}
          >
            <DownloadSimple size={14} className="mr-2" />
            Download
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          {/* Delete option */}
          <DropdownMenuItem
            onClick={() => onDelete(source.id, source.name)}
            className="text-destructive focus:text-destructive"
          >
            <Trash size={14} className="mr-2" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Source Info - truncates when panel is narrow, expands when resized */}
      <div className="overflow-hidden">
        <div className="flex items-center gap-1.5">
          <p className="text-sm truncate" title={source.name}>
            {source.name}
          </p>
          {/* Stage chip — shows the AI's current pass over this source.
             Editorial language ("Queued / Reading / Indexing / Failed")
             matches the rest of NoobBook's voice and reads at a glance. */}
          {source.status !== 'ready' && (
            <SourceStageChip status={source.status} />
          )}
        </div>
        <div className="flex items-center gap-2">
          <p className="text-xs text-muted-foreground">
            {formatFileSize(source.file_size)}
          </p>
          {/* For error state, surface the failure reason inline; healthy
             stages already speak through the chip above. */}
          {source.status === 'error' && statusDisplay && (
            <span
              className={`text-xs ${statusDisplay.color} truncate max-w-[140px]`}
              title={statusDisplay.tooltip}
            >
              {statusDisplay.tooltip}
            </span>
          )}
        </div>
      </div>

      {/* Checkbox + Freshdesk actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {/* Active Checkbox */}
        <Checkbox
          checked={source.active}
          onCheckedChange={(checked) => onToggleActive(source.id, checked === true)}
          disabled={!canToggleActive}
          className={`flex-shrink-0 ${!canToggleActive ? 'opacity-30' : ''}`}
          title={canToggleActive ? (source.active ? 'Click to exclude from chat' : 'Click to include in chat') : 'Source must be processed first'}
        />
      </div>

      {/* Status Icon for non-ready states */}
      {statusDisplay && source.status !== 'ready' && (
        <>
          {isActivelyWorking ? (
            // Processing or Embedding state: show spinner by default, stop icon on hover
            <button
              onClick={() => onCancelProcessing(source.id)}
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-destructive/10 transition-colors"
              title={isEmbedding ? 'Click to stop embedding' : 'Click to stop processing'}
            >
              {/* Spinner - visible by default, hidden on hover */}
              <CircleNotch
                size={16}
                className={`${isEmbedding ? 'text-blue-500' : 'text-primary'} animate-spin group-hover:hidden`}
              />
              {/* Stop icon - hidden by default, visible on hover */}
              <Stop
                size={16}
                weight="fill"
                className="text-destructive hidden group-hover:block"
              />
            </button>
          ) : isWaitingToProcess ? (
            // Uploaded/cancelled state: show retry icon to start processing
            <button
              onClick={() => onRetryProcessing(source.id)}
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-accent transition-colors"
              title="Click to start processing"
            >
              <ArrowsClockwise
                size={16}
                weight="bold"
                className="text-muted-foreground group-hover:text-primary"
              />
            </button>
          ) : (
            // Error state: show warning icon with retry button
            <button
              onClick={() => onRetryProcessing(source.id)}
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-accent transition-colors"
              title={statusDisplay?.tooltip || 'Click to retry processing'}
            >
              {/* Warning - visible by default, hidden on hover */}
              <Warning
                size={16}
                className="text-destructive group-hover:hidden"
              />
              {/* Retry icon - hidden by default, visible on hover */}
              <ArrowsClockwise
                size={16}
                weight="bold"
                className="text-primary hidden group-hover:block"
              />
            </button>
          )}
        </>
      )}
    </div>

      {/* Freshdesk sync action bar — visible for ready or syncing Freshdesk sources */}
      {isFreshdesk && (source.status === 'ready' || isSyncing) && (onSyncFreshdesk || onBackfillFreshdesk) && (
        <div className="flex items-center gap-2 px-2 pb-2 -mt-1">
          {onSyncFreshdesk && (
            <button
              onClick={(e) => { e.stopPropagation(); onSyncFreshdesk(source.id); }}
              disabled={isSyncing}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors ${
                isSyncing
                  ? 'bg-amber-50/50 text-amber-400 border-amber-100 cursor-not-allowed'
                  : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-200'
              }`}
            >
              {isSyncing ? <CircleNotch size={13} className="animate-spin" /> : <CloudArrowDown size={13} weight="bold" />}
              {isSyncing ? 'Syncing...' : 'Sync New'}
            </button>
          )}
          {onBackfillFreshdesk && (
            <button
              onClick={(e) => { e.stopPropagation(); setBackfillDialogOpen(true); }}
              disabled={isSyncing}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors ${
                isSyncing
                  ? 'bg-stone-50/50 text-stone-300 border-stone-100 cursor-not-allowed'
                  : 'bg-stone-50 text-stone-500 hover:bg-red-50 hover:text-red-600 border-stone-200 hover:border-red-200'
              }`}
            >
              <ArrowsClockwise size={13} />
              Re-sync All
            </button>
          )}
        </div>
      )}

      {/* Backfill Confirmation Dialog */}
      <AlertDialog open={backfillDialogOpen} onOpenChange={setBackfillDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <ArrowsClockwise size={20} className="text-amber-600" />
              Re-sync Freshdesk Tickets
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will <strong>clear all synced tickets</strong> and re-fetch the last 90 days from Freshdesk. If you only need the latest updates, use the <strong>sync button</strong> instead — it fetches only new and updated tickets without clearing existing data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setBackfillDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setBackfillDialogOpen(false);
                onBackfillFreshdesk?.(source.id);
              }}
            >
              Re-sync All Tickets
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
