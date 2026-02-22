/**
 * ComponentListItem Component
 * Educational Note: Renders a saved component job in the Generated Content list.
 */

import React from 'react';
import { SquaresFour } from '@phosphor-icons/react';
import type { ComponentJob } from '@/lib/api/studio';

interface ComponentListItemProps {
  job: ComponentJob;
  onClick: () => void;
}

export const ComponentListItem: React.FC<ComponentListItemProps> = ({ job, onClick }) => {
  const componentCount = job.components?.length || 0;
  const displayText = componentCount > 0
    ? `${componentCount} Component${componentCount !== 1 ? 's' : ''}`
    : job.component_description || 'Components';

  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-purple-500/10 rounded-md flex-shrink-0">
        <SquaresFour size={16} className="text-purple-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {displayText}
        </p>
      </div>
    </div>
  );
};
