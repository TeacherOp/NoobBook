/**
 * FlashCardListItem Component
 * Educational Note: Renders a saved flash card deck in the Generated Content list.
 */

import React from 'react';
import { Cards } from '@phosphor-icons/react';
import type { FlashCardJob } from '@/lib/api/studio';

interface FlashCardListItemProps {
  job: FlashCardJob;
  onClick: () => void;
}

export const FlashCardListItem: React.FC<FlashCardListItemProps> = ({ job, onClick }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-purple-500/10 rounded-md flex-shrink-0">
        <Cards size={16} className="text-purple-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">{job.source_name}</p>
      </div>
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.card_count}
      </span>
    </div>
  );
};
