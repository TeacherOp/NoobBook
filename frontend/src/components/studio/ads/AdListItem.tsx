import React from 'react';
import { Image, Trash } from '@phosphor-icons/react';
import type { AdJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface AdListItemProps {
  job: AdJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: AdJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  if (direction) return { title: direction, direction: null };
  const product = truncateForTitle(job.product_name);
  if (product) return { title: product, direction };
  return { title: 'Ad creatives', direction };
};

export const AdListItem: React.FC<AdListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-green-500/10 rounded-md flex-shrink-0">
        <Image size={16} className="text-green-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.images.length}
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
