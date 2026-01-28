/**
 * WebsiteSection Component
 * Educational Note: Self-contained section for website generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useWebsiteGeneration } from '../website/useWebsiteGeneration';
import { WebsiteListItem } from '../website/WebsiteListItem';
import { WebsiteProgressIndicator } from '../website/WebsiteProgressIndicator';
import { WebsiteViewerModal } from '../website/WebsiteViewerModal';

export const WebsiteSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedWebsiteJobs,
    currentWebsiteJob,
    isGeneratingWebsite,
    viewingWebsiteJob,
    setViewingWebsiteJob,
    loadSavedJobs,
    handleWebsiteGeneration,
    downloadWebsite,
  } = useWebsiteGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedWebsiteJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleWebsiteGeneration>[0]) => {
    await handleWebsiteGeneration(signal);
  }, [handleWebsiteGeneration]);

  useEffect(() => {
    registerGenerationHandler('website', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingWebsite) {
    return null;
  }

  return (
    <>
      {isGeneratingWebsite && (
        <WebsiteProgressIndicator currentWebsiteJob={currentWebsiteJob} />
      )}

      {filteredJobs.map((job) => (
        <WebsiteListItem
          key={job.id}
          job={job}
          onOpen={() => setViewingWebsiteJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadWebsite(job.id);
          }}
        />
      ))}

      <WebsiteViewerModal
        projectId={projectId}
        viewingWebsiteJob={viewingWebsiteJob}
        onClose={() => setViewingWebsiteJob(null)}
      />
    </>
  );
};
