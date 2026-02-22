/**
 * BlogProgressIndicator Component
 * Educational Note: Shows progress during blog post generation.
 * Displays status message and animated indicator. Uses indigo/blue theme.
 */

import React from 'react';
import { Article, Spinner } from '@phosphor-icons/react';
import type { BlogJob } from '@/lib/api/studio';

interface BlogProgressIndicatorProps {
  currentBlogJob: BlogJob | null;
}

export const BlogProgressIndicator: React.FC<BlogProgressIndicatorProps> = ({ currentBlogJob }) => {
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

  return (
    <div className="flex items-center gap-2 p-1.5 bg-indigo-50 dark:bg-indigo-950/30 rounded border border-indigo-200 dark:border-indigo-800/50">
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
    </div>
  );
};
