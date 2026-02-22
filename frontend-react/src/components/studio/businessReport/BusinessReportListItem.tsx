/**
 * BusinessReportListItem Component
 * Educational Note: Renders saved business reports in the Generated Content list.
 * Shows title, chart count, and word count. Uses teal/green theme.
 */

import React from 'react';
import { ChartBar, DownloadSimple } from '@phosphor-icons/react';
import type { BusinessReportJob } from '@/lib/api/studio';

interface BusinessReportListItemProps {
  job: BusinessReportJob;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
}

export const BusinessReportListItem: React.FC<BusinessReportListItemProps> = ({ job, onOpen, onDownload }) => {
  // Format word count for display
  const wordCountDisplay = job.word_count
    ? job.word_count >= 1000
      ? `${(job.word_count / 1000).toFixed(1)}k`
      : `${job.word_count}`
    : '-';

  const chartCount = job.charts?.length || 0;

  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="p-1.5 bg-teal-500/10 rounded-md flex-shrink-0">
        <ChartBar size={16} className="text-teal-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.title || job.source_name}
        </p>
      </div>
      {chartCount > 0 && (
        <span className="text-[11px] text-teal-600 flex-shrink-0">
          {chartCount} chart{chartCount > 1 ? 's' : ''}
        </span>
      )}
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {wordCountDisplay}w
      </span>
      <button
        onClick={onDownload}
        className="p-1 hover:bg-muted rounded flex-shrink-0"
        title="Download Business Report"
      >
        <DownloadSimple size={14} className="text-muted-foreground" />
      </button>
    </div>
  );
};
