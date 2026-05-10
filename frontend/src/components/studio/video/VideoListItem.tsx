import React from 'react';
import { VideoCamera, DownloadSimple, Trash } from '@phosphor-icons/react';
import type { VideoJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface VideoListItemProps {
  job: VideoJob;
  iterationIndex: number;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

const resolveTitle = (job: VideoJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  if (direction) return { title: direction, direction: null };
  if (job.source_name?.trim()) return { title: job.source_name, direction };
  return { title: 'Video', direction };
};

export const VideoListItem: React.FC<VideoListItemProps> = ({
  job,
  iterationIndex,
  onOpen,
  onDownload,
  onDelete,
}) => {
  const { title, direction } = resolveTitle(job);
  const videoCount = job.videos?.length ?? 0;
  return (
    <div
      onClick={onOpen}
      className="group flex items-start gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 cursor-pointer transition-colors"
    >
      <VideoCamera size={16} weight="duotone" className="text-orange-600 mt-0.5 flex-shrink-0" />
      <IterationRowHeader
        title={title}
        direction={direction}
        sourceName={job.source_name ?? null}
        createdAt={job.created_at}
        iterationIndex={iterationIndex}
        isEdited={!!job.parent_job_id}
      />
      <span className="text-[11px] text-muted-foreground flex-shrink-0 mt-1">
        {videoCount > 0 ? `${videoCount}v · ` : ''}{job.aspect_ratio} · {job.duration_seconds}s
      </span>
      <button
        onClick={onDownload}
        className="p-1.5 hover:bg-orange-600/20 rounded transition-colors"
        title="Download Video"
      >
        <DownloadSimple size={14} className="text-orange-600" />
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
