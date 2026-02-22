/**
 * ComponentSection Component
 * Educational Note: Self-contained section for UI component generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useComponentGeneration } from '../components/useComponentGeneration';
import { ComponentListItem } from '../components/ComponentListItem';
import { ComponentProgressIndicator } from '../components/ComponentProgressIndicator';
import { ComponentViewerModal } from '../components/ComponentViewerModal';

export const ComponentSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedComponentJobs,
    currentComponentJob,
    isGeneratingComponents,
    viewingComponentJob,
    setViewingComponentJob,
    loadSavedJobs,
    handleComponentGeneration,
  } = useComponentGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedComponentJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleComponentGeneration>[0]) => {
    await handleComponentGeneration(signal);
  }, [handleComponentGeneration]);

  useEffect(() => {
    registerGenerationHandler('components', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingComponents) {
    return null;
  }

  return (
    <>
      {isGeneratingComponents && (
        <ComponentProgressIndicator currentComponentJob={currentComponentJob} />
      )}

      {filteredJobs.map((job) => (
        <ComponentListItem
          key={job.id}
          job={job}
          onClick={() => setViewingComponentJob(job)}
        />
      ))}

      <ComponentViewerModal
        projectId={projectId}
        viewingComponentJob={viewingComponentJob}
        onClose={() => setViewingComponentJob(null)}
      />
    </>
  );
};
