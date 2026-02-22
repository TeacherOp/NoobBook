/**
 * MarketingStrategyListItem Component
 * Educational Note: Renders saved marketing strategies in the Generated Content list.
 * Shows document title and section count. Uses emerald/teal theme.
 */

import React from 'react';
import { ChartLine, DownloadSimple } from '@phosphor-icons/react';
import type { MarketingStrategyJob } from '@/lib/api/studio';

interface MarketingStrategyListItemProps {
  job: MarketingStrategyJob;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
}

export const MarketingStrategyListItem: React.FC<MarketingStrategyListItemProps> = ({ job, onOpen, onDownload }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="p-1.5 bg-emerald-500/10 rounded-md flex-shrink-0">
        <ChartLine size={16} className="text-emerald-600" />
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
        title="Download Marketing Strategy"
      >
        <DownloadSimple size={14} className="text-muted-foreground" />
      </button>
    </div>
  );
};
