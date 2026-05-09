import React from 'react';
import { ChartPieSlice, Trash } from '@phosphor-icons/react';
import type { InfographicJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface InfographicListItemProps {
  job: InfographicJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: InfographicJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const topic = truncateForTitle(job.topic_title);
  if (topic) return { title: topic, direction };
  if (direction) return { title: direction, direction: null };
  return { title: 'Infographic', direction };
};

export const InfographicListItem: React.FC<InfographicListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-amber-500/10 rounded-md flex-shrink-0">
        <ChartPieSlice size={16} className="text-amber-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
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
