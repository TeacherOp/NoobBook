/**
 * FlashCardProgressIndicator Component
 * Educational Note: Shows real-time progress during flash card generation.
 * Purple theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { FlashCardJob } from '@/lib/api/studio';

interface FlashCardProgressIndicatorProps {
  currentFlashCardJob: FlashCardJob | null;
}

export const FlashCardProgressIndicator: React.FC<FlashCardProgressIndicatorProps> = ({
  currentFlashCardJob,
}) => {
  if (!currentFlashCardJob) return null;

  return (
    <div className="p-2 bg-purple-500/5 rounded-md border border-purple-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-purple-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentFlashCardJob.source_name || 'Generating flash cards...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentFlashCardJob.progress || 'Starting...'}
          </p>
        </div>
      </div>
    </div>
  );
};
