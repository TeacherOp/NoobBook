/**
 * VideoViewerModal Component
 * Educational Note: Modal for playing generated videos with HTML5 video player.
 * Supports multiple videos per job (if user requested more than one).
 */

import React, { useState } from 'react';
import { DownloadSimple, PlayCircle, CaretLeft, CaretRight } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import type { VideoJob } from '@/lib/api/studio';
import { videosAPI } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

interface VideoViewerModalProps {
  projectId: string;
  viewingVideoJob: VideoJob | null;
  onClose: () => void;
  onDownload: (filename: string) => void;
}

export const VideoViewerModal: React.FC<VideoViewerModalProps> = ({
  projectId,
  viewingVideoJob,
  onClose,
  onDownload,
}) => {
  const [currentVideoIndex, setCurrentVideoIndex] = useState(0);

  if (!viewingVideoJob || !viewingVideoJob.videos.length) return null;

  const currentVideo = viewingVideoJob.videos[currentVideoIndex];
  const hasMultipleVideos = viewingVideoJob.videos.length > 1;

  const handlePrevVideo = () => {
    setCurrentVideoIndex((prev) => (prev > 0 ? prev - 1 : viewingVideoJob.videos.length - 1));
  };

  const handleNextVideo = () => {
    setCurrentVideoIndex((prev) => (prev < viewingVideoJob.videos.length - 1 ? prev + 1 : 0));
  };

  return (
    <Dialog
      open={!!viewingVideoJob}
      onOpenChange={(open) => {
        if (!open) {
          setCurrentVideoIndex(0);
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-4xl p-0 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b flex-shrink-0">
          <DialogHeader className="mb-2">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-orange-500/10 rounded">
                <PlayCircle size={20} weight="duotone" className="text-orange-600" />
              </div>
              <div>
                <DialogTitle className="text-lg">
                  {viewingVideoJob.source_name || 'Video'}
                </DialogTitle>
              </div>
            </div>
            <DialogDescription>
              {viewingVideoJob.videos.length} video{viewingVideoJob.videos.length > 1 ? 's' : ''} •
              {' '}{viewingVideoJob.aspect_ratio} • {viewingVideoJob.duration_seconds}s
            </DialogDescription>
          </DialogHeader>

          {/* Video navigation for multiple videos */}
          {hasMultipleVideos && (
            <div className="flex items-center justify-between mt-3 mb-2">
              <button
                onClick={handlePrevVideo}
                className="px-2 py-1 text-xs bg-orange-500/10 hover:bg-orange-500/20 text-orange-700 rounded transition-colors flex items-center gap-1"
              >
                <CaretLeft size={14} />
                Previous
              </button>
              <span className="text-xs text-gray-600">
                Video {currentVideoIndex + 1} of {viewingVideoJob.videos.length}
              </span>
              <button
                onClick={handleNextVideo}
                className="px-2 py-1 text-xs bg-orange-500/10 hover:bg-orange-500/20 text-orange-700 rounded transition-colors flex items-center gap-1"
              >
                Next
                <CaretRight size={14} />
              </button>
            </div>
          )}

          {/* Download current video */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => onDownload(currentVideo.filename)}
              className="px-3 py-1.5 text-xs bg-orange-600 hover:bg-orange-700 text-white rounded transition-colors flex items-center gap-1.5"
            >
              <DownloadSimple size={14} />
              Download Video
            </button>
          </div>
        </div>

        {/* Video Player */}
        <div className="flex-1 bg-black flex items-center justify-center">
          <video
            key={currentVideo.filename}
            controls
            autoPlay
            className="max-w-full max-h-[60vh]"
            src={getAuthUrl(videosAPI.getPreviewUrl(projectId, viewingVideoJob.id, currentVideo.filename))}
          >
            Your browser does not support the video tag.
          </video>
        </div>

        {/* Footer Info */}
        <div className="px-6 py-3 border-t bg-gray-50/50 flex-shrink-0">
          {viewingVideoJob.generated_prompt && (
            <p className="text-xs text-muted-foreground mb-2">
              <span className="font-medium">Generated Prompt:</span> {viewingVideoJob.generated_prompt}
            </p>
          )}
          {viewingVideoJob.direction && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">User Direction:</span> {viewingVideoJob.direction}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
