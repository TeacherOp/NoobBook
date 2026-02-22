/**
 * PRDListItem Component
 * Educational Note: Renders saved PRDs in the Generated Content list.
 * Shows document title and section count.
 */

import React from 'react';
import { FileText, DownloadSimple } from '@phosphor-icons/react';
import type { PRDJob } from '@/lib/api/studio';

interface PRDListItemProps {
  job: PRDJob;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
}

export const PRDListItem: React.FC<PRDListItemProps> = ({ job, onOpen, onDownload }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="p-1.5 bg-amber-500/10 rounded-md flex-shrink-0">
        <FileText size={16} className="text-amber-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.document_title || job.source_name}
        </p>
      </div>
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.sections_written}s
      </span>
      <button
        onClick={onDownload}
        className="p-1 hover:bg-muted rounded flex-shrink-0"
        title="Download PRD"
      >
        <DownloadSimple size={14} className="text-muted-foreground" />
      </button>
    </div>
  );
};
