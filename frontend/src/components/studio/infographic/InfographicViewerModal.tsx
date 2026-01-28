/**
 * InfographicViewerModal Component
 * Educational Note: Modal for viewing and downloading infographics.
 * Displays full-size image with hover download, key sections, and source info.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { ChartPieSlice, DownloadSimple } from '@phosphor-icons/react';
import type { InfographicJob } from '@/lib/api/studio';
import { API_HOST } from '@/lib/api/client';

interface InfographicViewerModalProps {
  viewingInfographicJob: InfographicJob | null;
  onClose: () => void;
}

export const InfographicViewerModal: React.FC<InfographicViewerModalProps> = ({
  viewingInfographicJob,
  onClose,
}) => {
  return (
    <Dialog open={viewingInfographicJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ChartPieSlice size={20} className="text-amber-600" />
            {viewingInfographicJob?.topic_title || 'Infographic'}
          </DialogTitle>
          {viewingInfographicJob?.topic_summary && (
            <DialogDescription>
              {viewingInfographicJob.topic_summary}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Infographic Image */}
        {viewingInfographicJob?.image_url && (
          <div className="py-4">
            <div className="relative group rounded-lg overflow-hidden border bg-muted">
              <img
                src={`${API_HOST}${viewingInfographicJob.image_url}`}
                alt={viewingInfographicJob.topic_title || 'Infographic'}
                className="w-full h-auto object-contain"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <Button
                  size="sm"
                  variant="secondary"
                  className="gap-1"
                  onClick={() => {
                    if (viewingInfographicJob?.image?.filename) {
                      const link = document.createElement('a');
                      link.href = `${API_HOST}${viewingInfographicJob.image_url}`;
                      link.download = viewingInfographicJob.image.filename;
                      link.click();
                    }
                  }}
                >
                  <DownloadSimple size={14} />
                  Download
                </Button>
              </div>
            </div>

            {/* Key Sections */}
            {viewingInfographicJob.key_sections && viewingInfographicJob.key_sections.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">Key Sections</h4>
                <div className="flex flex-wrap gap-2">
                  {viewingInfographicJob.key_sections.map((section, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded text-xs"
                    >
                      {section.title}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Source info */}
            <p className="text-xs text-muted-foreground mt-4">
              Generated from: {viewingInfographicJob.source_name}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
