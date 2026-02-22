/**
 * WireframeProgressIndicator Component
 * Educational Note: Shows real-time progress during wireframe generation.
 * Purple theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { WireframeJob } from '@/lib/api/studio/wireframes';

interface WireframeProgressIndicatorProps {
  currentWireframeJob: WireframeJob | null;
}

export const WireframeProgressIndicator: React.FC<WireframeProgressIndicatorProps> = ({
  currentWireframeJob,
}) => {
  if (!currentWireframeJob) return null;

  return (
    <div className="p-2 bg-purple-500/5 rounded-md border border-purple-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-purple-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentWireframeJob.source_name || 'Generating wireframe...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentWireframeJob.progress || 'Starting...'}
          </p>
        </div>
      </div>
    </div>
  );
};
