/**
 * BlogListItem Component
 * Educational Note: Renders saved blog posts in the Generated Content list.
 * Shows title and word count. Uses indigo/blue theme.
 */

import React from 'react';
import { Article, DownloadSimple } from '@phosphor-icons/react';
import type { BlogJob } from '@/lib/api/studio';

interface BlogListItemProps {
  job: BlogJob;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
}

export const BlogListItem: React.FC<BlogListItemProps> = ({ job, onOpen, onDownload }) => {
  // Format word count for display
  const wordCountDisplay = job.word_count
    ? job.word_count >= 1000
      ? `${(job.word_count / 1000).toFixed(1)}k`
      : `${job.word_count}`
    : '-';

  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="p-1.5 bg-indigo-500/10 rounded-md flex-shrink-0">
        <Article size={16} className="text-indigo-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.title || job.source_name}
        </p>
      </div>
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {wordCountDisplay}w
      </span>
      <button
        onClick={onDownload}
        className="p-1 hover:bg-muted rounded flex-shrink-0"
        title="Download Blog Post"
      >
        <DownloadSimple size={14} className="text-muted-foreground" />
      </button>
    </div>
  );
};
