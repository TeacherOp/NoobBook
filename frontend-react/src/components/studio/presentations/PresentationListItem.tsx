/**
 * PresentationListItem Component
 * Educational Note: Renders a saved presentation in the Generated Content list.
 * Clicking opens presentation in viewer modal. Download button downloads PPTX.
 */

import React from 'react';
import { Presentation, DownloadSimple } from '@phosphor-icons/react';
import type { PresentationJob } from '@/lib/api/studio';

interface PresentationListItemProps {
  job: PresentationJob;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
}

export const PresentationListItem: React.FC<PresentationListItemProps> = ({
  job,
  onOpen,
  onDownload,
}) => {
  return (
    <div
      onClick={onOpen}
      className="flex items-start gap-2.5 p-2.5 rounded-lg hover:bg-amber-500/10 cursor-pointer transition-colors"
    >
      <Presentation size={16} weight="duotone" className="text-amber-600 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-900 truncate">
          {job.presentation_title || 'Presentation'}
        </p>
        <p className="text-[11px] text-gray-500 truncate">
          {job.total_slides || job.slides_created || 0} slides
          {job.presentation_type && ` • ${job.presentation_type}`}
        </p>
      </div>
      {/* Download PPTX button */}
      <button
        onClick={onDownload}
        className="p-1.5 hover:bg-amber-600/20 rounded transition-colors"
        title="Download PPTX"
      >
        <DownloadSimple size={14} className="text-amber-600" />
      </button>
    </div>
  );
};
