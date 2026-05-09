/**
 * PresentationSection Component
 * Educational Note: Self-contained section for presentation generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { usePresentationGeneration } from '../presentations/usePresentationGeneration';
import { PresentationListItem } from '../presentations/PresentationListItem';
import { PresentationProgressIndicator } from '../presentations/PresentationProgressIndicator';
import { PresentationViewerModal } from '../presentations/PresentationViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const PresentationSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedPresentationJobs,
    currentPresentationJob,
    isGeneratingPresentation,
    viewingPresentationJob,
    setViewingPresentationJob,
    configError,
    pendingEditInput,
    loadSavedJobs,
    handlePresentationGeneration,
    handlePresentationEdit,
    handlePresentationDelete,
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

  if (filteredJobs.length === 0 && !isGeneratingPresentation && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingPresentation && (
        <PresentationProgressIndicator currentPresentationJob={currentPresentationJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <PresentationListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onOpen={() => setViewingPresentationJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadPresentation(job.id);
          }}
          onDelete={() => handlePresentationDelete(job.id)}
        />
      ))}

      <PresentationViewerModal
        projectId={projectId}
        viewingPresentationJob={viewingPresentationJob}
        onClose={() => setViewingPresentationJob(null)}
        onDownloadPptx={downloadPresentation}
        onEdit={(instructions) => viewingPresentationJob && handlePresentationEdit(viewingPresentationJob, instructions)}
        isGenerating={isGeneratingPresentation}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
