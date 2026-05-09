import React from 'react';
import { FileText, DownloadSimple, Trash } from '@phosphor-icons/react';
import type { PRDJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface PRDListItemProps {
  job: PRDJob;
  iterationIndex: number;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

const resolveTitle = (job: PRDJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const docTitle = truncateForTitle(job.document_title);
  const product = truncateForTitle(job.product_name);
  if (docTitle) return { title: docTitle, direction };
  if (product) return { title: product, direction };
  if (direction) return { title: direction, direction: null };
  if (job.source_name?.trim()) return { title: job.source_name, direction };
  return { title: 'PRD', direction };
};

export const PRDListItem: React.FC<PRDListItemProps> = ({ job, iterationIndex, onOpen, onDownload, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="p-1.5 bg-amber-500/10 rounded-md flex-shrink-0">
        <FileText size={16} className="text-amber-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
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
