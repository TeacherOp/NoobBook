/**
 * PresentationSection Component
 * Educational Note: Self-contained section for presentation generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { usePresentationGeneration } from '../presentations/usePresentationGeneration';
import { PresentationListItem } from '../presentations/PresentationListItem';
import { PresentationProgressIndicator } from '../presentations/PresentationProgressIndicator';
import { PresentationViewerModal } from '../presentations/PresentationViewerModal';

export const PresentationSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedPresentationJobs,
    currentPresentationJob,
    isGeneratingPresentation,
    viewingPresentationJob,
    setViewingPresentationJob,
    loadSavedJobs,
    handlePresentationGeneration,
    downloadPresentation,
  } = usePresentationGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedPresentationJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handlePresentationGeneration>[0]) => {
    await handlePresentationGeneration(signal);
  }, [handlePresentationGeneration]);

  useEffect(() => {
    registerGenerationHandler('presentation', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingPresentation) {
    return null;
  }

  return (
    <>
      {isGeneratingPresentation && (
        <PresentationProgressIndicator currentPresentationJob={currentPresentationJob} />
      )}

      {filteredJobs.map((job) => (
        <PresentationListItem
          key={job.id}
          job={job}
          onOpen={() => setViewingPresentationJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadPresentation(job.id);
          }}
        />
      ))}

      <PresentationViewerModal
        projectId={projectId}
        viewingPresentationJob={viewingPresentationJob}
        onClose={() => setViewingPresentationJob(null)}
        onDownloadPptx={downloadPresentation}
      />
    </>
  );
};
