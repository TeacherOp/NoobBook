import React from 'react';
import { Cube, Trash } from '@phosphor-icons/react';
import type { ComponentJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface ComponentListItemProps {
  job: ComponentJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: ComponentJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const description = truncateForTitle(job.component_description);
  if (description) return { title: description, direction };
  if (direction) return { title: direction, direction: null };
  return { title: 'Components', direction };
};

export const ComponentListItem: React.FC<ComponentListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  const componentCount = job.components?.length || 0;
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-purple-500/10 rounded-md flex-shrink-0">
        <Cube size={16} className="text-purple-600" />
      </div>
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      {componentCount > 0 && (
        <span className="text-[11px] text-muted-foreground flex-shrink-0">
          {componentCount}
        </span>
      )}
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
