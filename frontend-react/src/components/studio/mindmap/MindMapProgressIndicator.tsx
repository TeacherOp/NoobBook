/**
 * MindMapProgressIndicator Component
 * Educational Note: Shows real-time progress during mind map generation.
 * Blue theme distinguishes mind maps from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { MindMapJob } from '@/lib/api/studio';

interface MindMapProgressIndicatorProps {
  currentMindMapJob: MindMapJob | null;
}

export const MindMapProgressIndicator: React.FC<MindMapProgressIndicatorProps> = ({
  currentMindMapJob,
}) => {
  if (!currentMindMapJob) return null;

  return (
    <div className="p-2 bg-blue-500/5 rounded-md border border-blue-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-blue-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentMindMapJob.source_name || 'Generating mind map...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentMindMapJob.progress || 'Starting...'}
          </p>
        </div>
      </div>
    </div>
  );
};
