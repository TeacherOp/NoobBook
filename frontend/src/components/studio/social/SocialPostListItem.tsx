import React from 'react';
import { ShareNetwork, Trash } from '@phosphor-icons/react';
import type { SocialPostJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface SocialPostListItemProps {
  job: SocialPostJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: SocialPostJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const topic = truncateForTitle(job.topic);
  if (topic) return { title: topic, direction };
  if (direction) return { title: direction, direction: null };
  return { title: 'Social posts', direction };
};

export const SocialPostListItem: React.FC<SocialPostListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-cyan-500/10 rounded-md flex-shrink-0">
        <ShareNetwork size={16} className="text-cyan-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.post_count}
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
