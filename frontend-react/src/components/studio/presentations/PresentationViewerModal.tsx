/**
 * PresentationViewerModal Component
 * Educational Note: Modal for previewing generated presentations with slide navigation.
 * Shows screenshot images with PPTX download option.
 */

import React, { useState, useEffect } from 'react';
import {
  DownloadSimple,
  Presentation,
  CaretLeft,
  CaretRight,
} from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { presentationsAPI, type PresentationJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

interface PresentationViewerModalProps {
  projectId: string;
  viewingPresentationJob: PresentationJob | null;
  onClose: () => void;
  onDownloadPptx?: (jobId: string) => void;
  onDownloadSource?: (jobId: string) => void;
}

export const PresentationViewerModal: React.FC<PresentationViewerModalProps> = ({
  projectId,
  viewingPresentationJob,
  onClose,
  onDownloadPptx,
}) => {
  const [currentSlide, setCurrentSlide] = useState(1);
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);

  // Reset to first slide when opening a new presentation
  useEffect(() => {
    if (viewingPresentationJob) {
      setCurrentSlide(1);
    }
  }, [viewingPresentationJob?.id]);

  // Load screenshot URL when slide changes
  useEffect(() => {
    if (viewingPresentationJob && viewingPresentationJob.screenshots?.length > 0) {
      const screenshot = viewingPresentationJob.screenshots[currentSlide - 1];
      if (screenshot && screenshot.screenshot_file) {
        // API_BASE_URL already includes /api/v1 path, getAuthUrl adds JWT for browser element auth
        const url = getAuthUrl(presentationsAPI.getScreenshotUrl(
          projectId,
          viewingPresentationJob.id,
          screenshot.screenshot_file
        ));
        setScreenshotUrl(url);
      }
    }
  }, [viewingPresentationJob, currentSlide, projectId]);

  if (!viewingPresentationJob) return null;

  const totalSlides = viewingPresentationJob.screenshots?.length || 0;

  const handlePrevSlide = () => {
    if (currentSlide > 1) {
      setCurrentSlide((prev) => prev - 1);
    }
  };

  const handleNextSlide = () => {
    if (currentSlide < totalSlides) {
      setCurrentSlide((prev) => prev + 1);
    }
  };

  const handleDownloadPptx = () => {
    if (onDownloadPptx) {
      onDownloadPptx(viewingPresentationJob.id);
    } else {
      const link = document.createElement('a');
      // API_BASE_URL already includes /api/v1 path, getAuthUrl adds JWT for browser element auth
      link.href = getAuthUrl(presentationsAPI.getDownloadUrl(
        projectId,
        viewingPresentationJob.id,
        'pptx'
      ));
      link.click();
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      handlePrevSlide();
    } else if (e.key === 'ArrowRight') {
      handleNextSlide();
    }
  };

  return (
    <Dialog open={!!viewingPresentationJob} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="sm:max-w-6xl h-[85vh] p-0 overflow-hidden flex flex-col"
        onKeyDown={handleKeyDown}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex-shrink-0">
          <DialogHeader className="mb-2">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-amber-500/10 rounded">
                <Presentation size={20} weight="duotone" className="text-amber-600" />
              </div>
              <div>
                <DialogTitle className="text-lg">
                  {viewingPresentationJob.presentation_title || 'Presentation'}
                </DialogTitle>
              </div>
            </div>
            <DialogDescription>
              {totalSlides} slides
              {viewingPresentationJob.presentation_type &&
                ` | ${viewingPresentationJob.presentation_type}`}
              {viewingPresentationJob.target_audience &&
                ` | For: ${viewingPresentationJob.target_audience}`}
            </DialogDescription>
          </DialogHeader>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadPptx}
              className="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-700 text-white rounded transition-colors flex items-center gap-1.5"
            >
              <DownloadSimple size={14} />
              Download PPTX
            </button>
          </div>
        </div>

        {/* Slide Preview - Shows Screenshot Image */}
        <div className="flex-1 min-h-0 bg-gray-900 relative flex items-center justify-center">
          {screenshotUrl ? (
            <img
              src={screenshotUrl}
              alt={`Slide ${currentSlide}`}
              className="max-w-full max-h-full object-contain"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              No slides available
            </div>
          )}

          {/* Navigation Controls */}
          {totalSlides > 1 && (
            <>
              {/* Previous Button */}
              <button
                onClick={handlePrevSlide}
                disabled={currentSlide === 1}
                className="absolute left-4 top-1/2 -translate-y-1/2 p-2 bg-white/90 hover:bg-white rounded-full shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <CaretLeft size={24} className="text-gray-700" />
              </button>

              {/* Next Button */}
              <button
                onClick={handleNextSlide}
                disabled={currentSlide === totalSlides}
                className="absolute right-4 top-1/2 -translate-y-1/2 p-2 bg-white/90 hover:bg-white rounded-full shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <CaretRight size={24} className="text-gray-700" />
              </button>
            </>
          )}
        </div>

        {/* Footer - Slide Counter */}
        <div className="px-6 py-3 border-t bg-gray-50/50 flex-shrink-0 flex items-center justify-between">
          <div className="text-xs text-muted-foreground max-w-[70%] truncate">
            {viewingPresentationJob.summary && (
              <span>
                <span className="font-medium">Summary:</span> {viewingPresentationJob.summary}
              </span>
            )}
          </div>
          <div className="text-sm font-medium text-gray-600">
            Slide {currentSlide} of {totalSlides}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
