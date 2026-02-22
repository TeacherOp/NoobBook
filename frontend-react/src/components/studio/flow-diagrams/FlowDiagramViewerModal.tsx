/**
 * FlowDiagramViewerModal Component
 * Educational Note: Full-screen modal for viewing generated Mermaid diagrams.
 * Maximizes viewing area for large diagrams with pan/zoom support.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import { FlowDiagramViewer } from './FlowDiagramViewer';
import type { FlowDiagramJob } from '@/lib/api/studio';

interface FlowDiagramViewerModalProps {
  job: FlowDiagramJob | null;
  onClose: () => void;
}

export const FlowDiagramViewerModal: React.FC<FlowDiagramViewerModalProps> = ({
  job,
  onClose,
}) => {
  if (!job || !job.mermaid_syntax) return null;

  return (
    <Dialog open={!!job} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[95vw] w-[95vw] h-[92vh] p-0 flex flex-col gap-0">
        {/* Compact header */}
        <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold">
              {job.title || 'Flow Diagram'}
            </h2>
            {job.diagram_type && (
              <span className="text-xs px-2 py-0.5 bg-cyan-100 text-cyan-700 rounded-full capitalize">
                {job.diagram_type}
              </span>
            )}
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

        {/* Full diagram viewer area */}
        <div className="flex-1 overflow-hidden">
          <FlowDiagramViewer
            mermaidSyntax={job.mermaid_syntax}
            description={job.description || undefined}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};
