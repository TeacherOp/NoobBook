import React from 'react';
import { Cards, Trash } from '@phosphor-icons/react';
import type { FlashCardJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface FlashCardListItemProps {
  job: FlashCardJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: FlashCardJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const summary = truncateForTitle(job.topic_summary);
  if (summary) return { title: summary, direction };
  if (direction) return { title: direction, direction: null };
  if (job.source_name?.trim()) return { title: job.source_name, direction };
  return { title: 'Flash cards', direction };
};

export const FlashCardListItem: React.FC<FlashCardListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-purple-500/10 rounded-md flex-shrink-0">
        <Cards size={16} className="text-purple-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.card_count}
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
