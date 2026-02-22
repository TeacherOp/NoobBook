/**
 * WireframeSection Component
 * Educational Note: Self-contained section for wireframe generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useWireframeGeneration } from '../wireframes/useWireframeGeneration';
import { WireframeListItem } from '../wireframes/WireframeListItem';
import { WireframeProgressIndicator } from '../wireframes/WireframeProgressIndicator';
import { WireframeViewerModal } from '../wireframes/WireframeViewerModal';

export const WireframeSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedWireframeJobs,
    currentWireframeJob,
    isGeneratingWireframe,
    viewingWireframeJob,
    setViewingWireframeJob,
    loadSavedJobs,
    handleWireframeGeneration,
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

  if (filteredJobs.length === 0 && !isGeneratingWireframe) {
    return null;
  }

  return (
    <>
      {isGeneratingWireframe && (
        <WireframeProgressIndicator currentWireframeJob={currentWireframeJob} />
      )}

      {filteredJobs.map((job) => (
        <WireframeListItem
          key={job.id}
          job={job}
          onClick={() => setViewingWireframeJob(job)}
        />
      ))}

      <WireframeViewerModal
        job={viewingWireframeJob}
        onClose={() => setViewingWireframeJob(null)}
      />
    </>
  );
};
