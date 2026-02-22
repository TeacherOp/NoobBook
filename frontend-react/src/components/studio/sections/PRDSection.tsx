/**
 * PRDSection Component
 * Educational Note: Self-contained section for PRD (Product Requirements Document) generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { usePRDGeneration } from '../prd/usePRDGeneration';
import { PRDListItem } from '../prd/PRDListItem';
import { PRDProgressIndicator } from '../prd/PRDProgressIndicator';
import { PRDViewerModal } from '../prd/PRDViewerModal';

export const PRDSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedPRDJobs,
    currentPRDJob,
    isGeneratingPRD,
    viewingPRDJob,
    setViewingPRDJob,
    loadSavedJobs,
    handlePRDGeneration,
    downloadPRD,
  } = usePRDGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedPRDJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handlePRDGeneration>[0]) => {
    await handlePRDGeneration(signal);
  }, [handlePRDGeneration]);

  useEffect(() => {
    registerGenerationHandler('prd', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingPRD) {
    return null;
  }

  return (
    <>
      {isGeneratingPRD && (
        <PRDProgressIndicator currentPRDJob={currentPRDJob} />
      )}

      {filteredJobs.map((job) => (
        <PRDListItem
          key={job.id}
          job={job}
          onOpen={() => setViewingPRDJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadPRD(job.id);
          }}
        />
      ))}

      <PRDViewerModal
        projectId={projectId}
        viewingPRDJob={viewingPRDJob}
        onClose={() => setViewingPRDJob(null)}
        onDownload={downloadPRD}
      />
    </>
  );
};
