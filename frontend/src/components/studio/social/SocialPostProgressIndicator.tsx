/**
 * SocialPostProgressIndicator Component
 * Educational Note: Shows real-time progress during social post generation.
 * Cyan theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { SocialPostJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface SocialPostProgressIndicatorProps {
  currentSocialPostJob: SocialPostJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const SocialPostProgressIndicator: React.FC<SocialPostProgressIndicatorProps> = ({
  currentSocialPostJob,
  projectId,
}) => {
  if (!currentSocialPostJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentSocialPostJob?.id) return;
    await cancelStudioJob(projectId, currentSocialPostJob.id);
  };

  return (
    <div className="p-2 bg-cyan-500/5 rounded-md border border-cyan-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-cyan-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentSocialPostJob.topic || 'Generating social posts...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentSocialPostJob.progress || 'Starting...'}
          </p>
        </div>
        {projectId && currentSocialPostJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
