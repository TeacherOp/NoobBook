/**
 * VideoProgressIndicator Component
 * Educational Note: Shows real-time progress during video generation using Google Veo 2.0.
 * Video generation can take 10-20 minutes, so we show detailed progress updates.
 * Orange theme distinguishes videos from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { VideoJob } from '@/lib/api/studio';

interface VideoProgressIndicatorProps {
  currentVideoJob: VideoJob | null;
}

export const VideoProgressIndicator: React.FC<VideoProgressIndicatorProps> = ({
  currentVideoJob,
}) => {
  if (!currentVideoJob) return null;

  return (
    <div className="p-2 bg-orange-500/5 rounded-md border border-orange-500/20">
      <div className="flex items-center gap-2">
        <SpinnerGap className="animate-spin text-orange-500" size={16} />
        <div className="flex-1">
          <p className="text-xs text-orange-700 font-medium">
            Generating video... ({currentVideoJob.number_of_videos} video{currentVideoJob.number_of_videos > 1 ? 's' : ''})
          </p>
          <p className="text-xs text-orange-600">
            {currentVideoJob.status_message || 'Starting...'}
          </p>
          {currentVideoJob.generated_prompt && (
            <p className="text-[10px] text-orange-500 mt-1 line-clamp-2">
              Prompt: {currentVideoJob.generated_prompt}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
