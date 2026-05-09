import React from 'react';
import { PresentationChart, DownloadSimple, Trash } from '@phosphor-icons/react';
import type { PresentationJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface PresentationListItemProps {
  job: PresentationJob;
  iterationIndex: number;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

const resolveTitle = (job: PresentationJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const presTitle = truncateForTitle(job.presentation_title);
  if (presTitle) return { title: presTitle, direction };
  if (direction) return { title: direction, direction: null };
  if (job.source_name?.trim()) return { title: job.source_name, direction };
  return { title: 'Presentation', direction };
};

export const PresentationListItem: React.FC<PresentationListItemProps> = ({
  job,
  iterationIndex,
  onOpen,
  onDownload,
  onDelete,
}) => {
  const { title, direction } = resolveTitle(job);
  const slideCount = job.total_slides || job.slides_created || 0;
  return (
    <div
      onClick={onOpen}
      className="group flex items-start gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 cursor-pointer transition-colors"
    >
      <PresentationChart size={16} weight="duotone" className="text-amber-600 mt-0.5 flex-shrink-0" />
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      {slideCount > 0 && (
        <span className="text-[11px] text-muted-foreground flex-shrink-0 mt-1">
          {slideCount} sl
        </span>
      )}
      <button
        onClick={onDownload}
        className="p-1.5 hover:bg-amber-600/20 rounded transition-colors"
        title="Download PPTX"
      >
        <DownloadSimple size={14} className="text-amber-600" />
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
