/**
 * WireframeViewerModal Component
 * Educational Note: Full-screen modal for viewing and editing wireframes.
 * Uses Excalidraw's built-in pan/zoom and editing capabilities.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import { WireframeViewer } from './WireframeViewer';
import type { WireframeJob } from '@/lib/api/studio/wireframes';

interface WireframeViewerModalProps {
  job: WireframeJob | null;
  onClose: () => void;
}

export const WireframeViewerModal: React.FC<WireframeViewerModalProps> = ({
  job,
  onClose,
}) => {
  if (!job || !job.elements || job.elements.length === 0) return null;

  return (
    <Dialog open={!!job} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[95vw] w-[95vw] h-[92vh] p-0 flex flex-col gap-0">
        {/* Compact header */}
        <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold">
              {job.title || 'Wireframe'}
            </h2>
            <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">
              wireframe
            </span>
            {job.source_name && (
              <span className="text-sm text-muted-foreground">
                from {job.source_name}
              </span>
            )}
            {job.generation_time_seconds && (
              <span className="text-xs text-muted-foreground">
                ({job.generation_time_seconds}s)
              </span>
            )}
          </div>
        </div>

        {/* Wireframe viewer - Excalidraw needs explicit non-zero dimensions */}
        <div style={{ flex: 1, height: 'calc(92vh - 50px)', width: '100%' }}>
          <WireframeViewer elements={job.elements} />
        </div>
      </DialogContent>
    </Dialog>
  );
};
