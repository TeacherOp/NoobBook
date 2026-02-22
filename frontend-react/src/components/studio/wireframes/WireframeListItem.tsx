/**
 * WireframeListItem Component
 * Educational Note: Renders a saved wireframe in the Generated Content list.
 * Clicking opens the wireframe in the Excalidraw viewer modal.
 */

import React from 'react';
import { Browser } from '@phosphor-icons/react';
import type { WireframeJob } from '@/lib/api/studio/wireframes';

interface WireframeListItemProps {
  job: WireframeJob;
  onClick: () => void;
}

export const WireframeListItem: React.FC<WireframeListItemProps> = ({ job, onClick }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-purple-500/10 rounded-md flex-shrink-0">
        <Browser size={16} className="text-purple-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.title || 'Wireframe'}
        </p>
        <p className="text-[11px] text-muted-foreground truncate">
          {job.element_count} elements
        </p>
      </div>
    </div>
  );
};
