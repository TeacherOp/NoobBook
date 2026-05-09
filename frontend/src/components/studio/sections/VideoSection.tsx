/**
 * VideoSection Component
 * Educational Note: Self-contained section for video generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { useVideoGeneration } from '../video/useVideoGeneration';
import { VideoListItem } from '../video/VideoListItem';
import { VideoProgressIndicator } from '../video/VideoProgressIndicator';
import { VideoViewerModal } from '../video/VideoViewerModal';

export const VideoSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedVideoJobs,
    currentVideoJob,
    isGeneratingVideo,
    viewingVideoJob,
    setViewingVideoJob,
    pendingEditInput,
    loadSavedJobs,
    handleVideoGeneration,
    handleVideoEdit,
    handleVideoDelete,
    downloadVideo,
  } = useVideoGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedVideoJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleVideoGeneration>[0]) => {
    await handleVideoGeneration(signal);
  }, [handleVideoGeneration]);

  useEffect(() => {
    registerGenerationHandler('video', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingVideo) {
    return null;
  }

  return (
    <>
      {isGeneratingVideo && (
        <VideoProgressIndicator currentVideoJob={currentVideoJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <VideoListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onOpen={() => setViewingVideoJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            if (job.videos.length > 0) {
              downloadVideo(job.id, job.videos[0].filename);
            }
          }}
          onDelete={() => handleVideoDelete(job.id)}
        />
      ))}

      <VideoViewerModal
        projectId={projectId}
        viewingVideoJob={viewingVideoJob}
        onClose={() => setViewingVideoJob(null)}
        onDownload={(filename) => {
          if (viewingVideoJob) {
            downloadVideo(viewingVideoJob.id, filename);
          }
        }}
        onEdit={(instructions) => viewingVideoJob && handleVideoEdit(viewingVideoJob, instructions)}
        isGenerating={isGeneratingVideo}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
