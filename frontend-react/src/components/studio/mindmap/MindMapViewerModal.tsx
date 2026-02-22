/**
 * MindMapViewerModal Component
 * Educational Note: Modal for viewing mind map tree visualization.
 * Uses MindMapViewer component for interactive node display.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { TreeStructure } from '@phosphor-icons/react';
import { MindMapViewer } from './MindMapViewer';
import type { MindMapJob } from '@/lib/api/studio';

interface MindMapViewerModalProps {
  viewingMindMapJob: MindMapJob | null;
  onClose: () => void;
}

export const MindMapViewerModal: React.FC<MindMapViewerModalProps> = ({
  viewingMindMapJob,
  onClose,
}) => {
  return (
    <Dialog open={viewingMindMapJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-5xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <TreeStructure size={20} className="text-blue-600" />
            {viewingMindMapJob?.source_name}
          </DialogTitle>
          {viewingMindMapJob?.topic_summary && (
            <DialogDescription>
              {viewingMindMapJob.topic_summary}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Mind Map Visualization */}
        <div className="flex-1 min-h-0">
          {viewingMindMapJob && (
            <MindMapViewer
              nodes={viewingMindMapJob.nodes}
              topicSummary={viewingMindMapJob.topic_summary}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
