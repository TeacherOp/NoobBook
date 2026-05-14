/**
 * BlogProgressIndicator Component
 * Educational Note: Shows progress during blog post generation.
 * Displays status message and animated indicator. Uses indigo/blue theme.
 */

import React from 'react';
import { Article, Spinner } from '@phosphor-icons/react';
import type { BlogJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface BlogProgressIndicatorProps {
  currentBlogJob: BlogJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const BlogProgressIndicator: React.FC<BlogProgressIndicatorProps> = ({ currentBlogJob, projectId }) => {
  // Determine progress message based on job state
  const getProgressMessage = () => {
    if (!currentBlogJob) return 'Starting blog post generation...';

    const status = currentBlogJob.status_message || 'Processing...';
    const imageCount = currentBlogJob.images?.length || 0;

    // Add image count if any images have been generated
    if (imageCount > 0) {
      return `${status} (${imageCount} image${imageCount > 1 ? 's' : ''} generated)`;
    }

    return status;
  };

  const handleCancel = async () => {
    if (!projectId || !currentBlogJob?.id) return;
    await cancelStudioJob(projectId, currentBlogJob.id);
  };

  return (
    <div className="flex flex-col gap-1.5 p-1.5 bg-indigo-50 dark:bg-indigo-950/30 rounded border border-indigo-200 dark:border-indigo-800/50">
      <div className="flex items-center gap-2">
        <div className="p-1 bg-indigo-500/10 rounded">
          <Spinner size={12} className="text-indigo-600 animate-spin" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-medium text-indigo-700 dark:text-indigo-400 truncate">
            {getProgressMessage()}
          </p>
          {currentBlogJob?.title && (
            <p className="text-[9px] text-indigo-600/70 dark:text-indigo-400/70 truncate">
              {currentBlogJob.title}
            </p>
          )}
        </div>
        <Article size={12} className="text-indigo-500 flex-shrink-0" />
        {projectId && currentBlogJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
