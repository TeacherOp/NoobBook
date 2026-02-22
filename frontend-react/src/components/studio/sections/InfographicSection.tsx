/**
 * InfographicSection Component
 * Educational Note: Self-contained section for infographic generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useInfographicGeneration } from '../infographic/useInfographicGeneration';
import { InfographicListItem } from '../infographic/InfographicListItem';
import { InfographicProgressIndicator } from '../infographic/InfographicProgressIndicator';
import { InfographicViewerModal } from '../infographic/InfographicViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const InfographicSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedInfographicJobs,
    currentInfographicJob,
    isGeneratingInfographic,
    viewingInfographicJob,
    setViewingInfographicJob,
    configError,
    loadSavedJobs,
    handleInfographicGeneration,
  } = useInfographicGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedInfographicJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleInfographicGeneration>[0]) => {
    await handleInfographicGeneration(signal);
  }, [handleInfographicGeneration]);

  useEffect(() => {
    registerGenerationHandler('infographics', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingInfographic && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingInfographic && (
        <InfographicProgressIndicator currentInfographicJob={currentInfographicJob} />
      )}

      {filteredJobs.map((job) => (
        <InfographicListItem
          key={job.id}
          job={job}
          onClick={() => setViewingInfographicJob(job)}
        />
      ))}

      <InfographicViewerModal
        viewingInfographicJob={viewingInfographicJob}
        onClose={() => setViewingInfographicJob(null)}
      />
    </>
  );
};
