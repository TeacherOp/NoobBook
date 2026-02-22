/**
 * AdProgressIndicator Component
 * Educational Note: Shows real-time progress during ad creative generation.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { AdJob } from '@/lib/api/studio';

interface AdProgressIndicatorProps {
  currentAdJob: AdJob | null;
}

export const AdProgressIndicator: React.FC<AdProgressIndicatorProps> = ({
  currentAdJob,
}) => {
  if (!currentAdJob) return null;

  return (
    <div className="p-2 bg-primary/5 rounded-md border border-primary/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-primary flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentAdJob.product_name || 'Generating ads...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentAdJob.progress || 'Starting...'}
          </p>
        </div>
      </div>
    </div>
  );
};
