/**
 * WireframeSection Component
 * Educational Note: Self-contained section for wireframe generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { useWireframeGeneration } from '../wireframes/useWireframeGeneration';
import { WireframeListItem } from '../wireframes/WireframeListItem';
import { WireframeProgressIndicator } from '../wireframes/WireframeProgressIndicator';
import { WireframeViewerModal } from '../wireframes/WireframeViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const WireframeSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedWireframeJobs,
    currentWireframeJob,
    isGeneratingWireframe,
    viewingWireframeJob,
    setViewingWireframeJob,
    configError,
    pendingEditInput,
    loadSavedJobs,
    handleWireframeGeneration,
    handleWireframeEdit,
    handleWireframeDelete,
  } = useWireframeGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedWireframeJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleWireframeGeneration>[0]) => {
    await handleWireframeGeneration(signal);
  }, [handleWireframeGeneration]);

  useEffect(() => {
    registerGenerationHandler('wireframes', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingWireframe && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingWireframe && (
        <WireframeProgressIndicator currentWireframeJob={currentWireframeJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <WireframeListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onClick={() => setViewingWireframeJob(job)}
          onDelete={() => handleWireframeDelete(job.id)}
        />
      ))}

      <WireframeViewerModal
        job={viewingWireframeJob}
        onClose={() => setViewingWireframeJob(null)}
        onEdit={(instructions) => viewingWireframeJob && handleWireframeEdit(viewingWireframeJob, instructions)}
        isGenerating={isGeneratingWireframe}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
