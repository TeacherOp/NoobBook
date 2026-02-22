/**
 * ComponentProgressIndicator Component
 * Educational Note: Shows real-time progress during component generation.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { ComponentJob } from '@/lib/api/studio';

interface ComponentProgressIndicatorProps {
  currentComponentJob: ComponentJob | null;
}

export const ComponentProgressIndicator: React.FC<ComponentProgressIndicatorProps> = ({
  currentComponentJob,
}) => {
  if (!currentComponentJob) return null;

  return (
    <div className="p-2 bg-blue-500/5 rounded-md border border-blue-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-blue-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentComponentJob.source_name || 'Generating components...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentComponentJob.status_message || 'Starting...'}
          </p>
        </div>
      </div>
    </div>
  );
};
