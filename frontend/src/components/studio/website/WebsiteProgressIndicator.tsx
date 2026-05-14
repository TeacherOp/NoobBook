/**
 * WebsiteProgressIndicator Component
 * Educational Note: Shows real-time progress during website generation.
 * Purple theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { WebsiteJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface WebsiteProgressIndicatorProps {
  currentWebsiteJob: WebsiteJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const WebsiteProgressIndicator: React.FC<WebsiteProgressIndicatorProps> = ({
  currentWebsiteJob,
  projectId,
}) => {
  if (!currentWebsiteJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentWebsiteJob?.id) return;
    await cancelStudioJob(projectId, currentWebsiteJob.id);
  };

  return (
    <div className="p-2 bg-purple-500/5 rounded-md border border-purple-500/20">
      <div className="flex items-center gap-2">
        <SpinnerGap className="animate-spin text-purple-500" size={16} />
        <div className="flex-1">
          <p className="text-xs text-purple-700 font-medium">
            {currentWebsiteJob.site_name || 'Generating website...'}
          </p>
          <p className="text-xs text-purple-600">
            {currentWebsiteJob.status_message || 'Starting...'}
          </p>
        </div>
        {projectId && currentWebsiteJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
