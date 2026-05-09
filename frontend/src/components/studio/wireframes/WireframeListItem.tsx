import React from 'react';
import { Layout, Trash } from '@phosphor-icons/react';
import type { WireframeJob } from '@/lib/api/studio/wireframes';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface WireframeListItemProps {
  job: WireframeJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: WireframeJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const title = truncateForTitle(job.title);
  if (title) return { title, direction };
  if (direction) return { title: direction, direction: null };
  return { title: 'Wireframe', direction };
};

export const WireframeListItem: React.FC<WireframeListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-purple-500/10 rounded-md flex-shrink-0">
        <Layout size={16} className="text-purple-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.element_count} el
      </span>
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
