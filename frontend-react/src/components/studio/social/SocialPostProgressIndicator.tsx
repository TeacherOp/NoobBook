/**
 * SocialPostProgressIndicator Component
 * Educational Note: Shows real-time progress during social post generation.
 * Cyan theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { SocialPostJob } from '@/lib/api/studio';

interface SocialPostProgressIndicatorProps {
  currentSocialPostJob: SocialPostJob | null;
}

export const SocialPostProgressIndicator: React.FC<SocialPostProgressIndicatorProps> = ({
  currentSocialPostJob,
}) => {
  if (!currentSocialPostJob) return null;

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
      </div>
    </div>
  );
};
