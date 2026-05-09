import React from 'react';
import { EnvelopeSimple, Trash } from '@phosphor-icons/react';
import type { EmailJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface EmailListItemProps {
  job: EmailJob;
  iterationIndex: number;
  onClick: () => void;
  onDelete: () => void;
}

const resolveTitle = (job: EmailJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const template = truncateForTitle(job.template_name);
  const subject = truncateForTitle(job.subject_line);
  if (template) return { title: template, direction };
  if (subject) return { title: subject, direction };
  if (direction) return { title: direction, direction: null };
  return { title: 'Email', direction };
};

export const EmailListItem: React.FC<EmailListItemProps> = ({ job, iterationIndex, onClick, onDelete }) => {
  const { title, direction } = resolveTitle(job);
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-blue-500/10 rounded-md flex-shrink-0">
        <EnvelopeSimple size={16} className="text-blue-600" />
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
