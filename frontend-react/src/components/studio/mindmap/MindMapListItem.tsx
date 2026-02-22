/**
 * MindMapListItem Component
 * Educational Note: Renders saved mind maps in the Generated Content list.
 */

import React from 'react';
import { TreeStructure } from '@phosphor-icons/react';
import type { MindMapJob } from '@/lib/api/studio';

interface MindMapListItemProps {
  job: MindMapJob;
  onClick: () => void;
}

export const MindMapListItem: React.FC<MindMapListItemProps> = ({ job, onClick }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-blue-500/10 rounded-md flex-shrink-0">
        <TreeStructure size={16} className="text-blue-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">{job.source_name}</p>
      </div>
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.node_count}
      </span>
    </div>
  );
};
