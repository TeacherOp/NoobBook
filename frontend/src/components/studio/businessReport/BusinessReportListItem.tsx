import React from 'react';
import { ChartBar, DownloadSimple, Trash } from '@phosphor-icons/react';
import type { BusinessReportJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface BusinessReportListItemProps {
  job: BusinessReportJob;
  iterationIndex: number;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

const resolveTitle = (job: BusinessReportJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const title = truncateForTitle(job.title);
  if (title) return { title, direction };
  if (direction) return { title: direction, direction: null };
  if (job.source_name?.trim()) return { title: job.source_name, direction };
  return { title: 'Business report', direction };
};

export const BusinessReportListItem: React.FC<BusinessReportListItemProps> = ({ job, iterationIndex, onOpen, onDownload, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  const wordCountDisplay = job.word_count
    ? job.word_count >= 1000
      ? `${(job.word_count / 1000).toFixed(1)}k`
      : `${job.word_count}`
    : '-';
  const chartCount = job.charts?.length || 0;
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="p-1.5 bg-teal-500/10 rounded-md flex-shrink-0">
        <ChartBar size={16} className="text-teal-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
        isEdited={!!job.parent_job_id}
      />
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
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="p-1 hover:bg-destructive/10 rounded flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Delete"
      >
        <Trash size={14} className="text-muted-foreground hover:text-destructive" />
      </button>
    </div>
  );
};
