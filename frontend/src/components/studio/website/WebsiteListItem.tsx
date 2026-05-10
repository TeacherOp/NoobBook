import React from 'react';
import { Globe, DownloadSimple, Trash } from '@phosphor-icons/react';
import type { WebsiteJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface WebsiteListItemProps {
  job: WebsiteJob;
  iterationIndex: number;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

const resolveTitle = (job: WebsiteJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  const siteName = truncateForTitle(job.site_name);
  if (siteName) return { title: siteName, direction };
  if (direction) return { title: direction, direction: null };
  return { title: 'Website', direction };
};

export const WebsiteListItem: React.FC<WebsiteListItemProps> = ({
  job,
  iterationIndex,
  onOpen,
  onDownload,
  onDelete,
}) => {
  const { title, direction } = resolveTitle(job);
  const pageCount = job.pages_created?.length ?? 0;
  const featureCount = job.features_implemented?.length ?? 0;
  const scopeParts = [
    pageCount > 0 ? `${pageCount} pg` : null,
    featureCount > 0 ? `${featureCount} ft` : null,
  ].filter(Boolean);
  return (
    <div
      onClick={onOpen}
      className="group flex items-start gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 cursor-pointer transition-colors"
    >
      <Globe size={16} weight="duotone" className="text-purple-600 mt-0.5 flex-shrink-0" />
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
      />
      {scopeParts.length > 0 && (
        <span className="text-[11px] text-muted-foreground flex-shrink-0 mt-1">
          {scopeParts.join(' · ')}
        </span>
      )}
      <button
        onClick={onDownload}
        className="p-1.5 hover:bg-purple-600/20 rounded transition-colors"
        title="Download ZIP"
      >
        <DownloadSimple size={14} className="text-purple-600" />
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
