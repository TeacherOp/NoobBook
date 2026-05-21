/**
 * LogsModal — admin diagnostic logs viewer in dialog form.
 *
 * Aesthetic direction: a small "operator's console" embedded inside the
 * warm cream chrome of the rest of the app. The dialog header stays in
 * the project palette (stone / amber); the log viewer panel itself
 * flips dark (stone-900) with monospace text and color-coded level
 * pills, signalling "this is the under-the-hood view." The contrast is
 * the differentiator — it reads as a real terminal, not just another
 * card.
 *
 * State + handlers come from `useLogsState`; the dark panel + filter
 * chips + action row are rendered by `LogConsole`. This file is the
 * Dialog wrapper only — the same pieces are reused in `LogsSection`
 * for the settings page.
 */
import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Bug } from '@phosphor-icons/react';
import { ToastContainer } from '../ui/toast';
import { LogConsole } from './LogConsole';
import { useLogsState } from './useLogsState';
import { DownloadLogsConfirmDialog } from './DownloadLogsConfirmDialog';

interface LogsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Whether to show the Clear logs button. Admins only; default true for backward compat. */
  canClear?: boolean;
}

export const LogsModal: React.FC<LogsModalProps> = ({ open, onOpenChange, canClear = true }) => {
  const state = useLogsState({ active: open });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[760px] max-h-[88vh] p-0 overflow-hidden flex flex-col">
        <div className="px-7 pt-6 pb-4 border-b flex-shrink-0">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-semibold pr-8">
              <Bug size={18} className="text-primary flex-shrink-0" />
              <span>Diagnostic logs</span>
            </DialogTitle>
            <DialogDescription className="text-xs leading-relaxed text-muted-foreground mt-1">
              Recent backend + frontend errors from this deployment. Download
              the bundle to share a complete snapshot with support — log files,
              env-var keys, and migration state are included.
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="flex-1 overflow-y-auto bg-stone-50 px-7 py-5">
          <LogConsole
            variant="modal"
            panelMaxHeightClassName="max-h-[55vh]"
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
            canClear={canClear}
            paused={state.paused}
            onTogglePaused={state.setPaused}
          />
        </div>

        <ToastContainer toasts={state.toasts} onDismiss={state.dismissToast} />

        <DownloadLogsConfirmDialog
          open={state.downloadDialogOpen}
          onOpenChange={state.setDownloadDialogOpen}
          deleteAfterDownload={state.deleteAfterDownload}
          onDeleteAfterDownloadChange={state.setDeleteAfterDownload}
          onConfirm={state.confirmDownload}
          canDelete={state.canDeleteLogs}
        />
      </DialogContent>
    </Dialog>
  );
};
