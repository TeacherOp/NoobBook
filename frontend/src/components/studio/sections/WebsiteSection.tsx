/**
 * WebsiteSection Component
 * Educational Note: Self-contained section for website generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { useWebsiteGeneration } from '../website/useWebsiteGeneration';
import { WebsiteListItem } from '../website/WebsiteListItem';
import { WebsiteProgressIndicator } from '../website/WebsiteProgressIndicator';
import { WebsiteViewerModal } from '../website/WebsiteViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const WebsiteSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedWebsiteJobs,
    currentWebsiteJob,
    isGeneratingWebsite,
    viewingWebsiteJob,
    setViewingWebsiteJob,
    configError,
    pendingEditInput,
    loadSavedJobs,
    handleWebsiteGeneration,
    handleWebsiteEdit,
    handleWebsiteDelete,
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

  if (filteredJobs.length === 0 && !isGeneratingWebsite && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingWebsite && (
        <WebsiteProgressIndicator currentWebsiteJob={currentWebsiteJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <WebsiteListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onOpen={() => setViewingWebsiteJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadWebsite(job.id);
          }}
          onDelete={() => handleWebsiteDelete(job.id)}
        />
      ))}

      <WebsiteViewerModal
        projectId={projectId}
        viewingWebsiteJob={viewingWebsiteJob}
        onClose={() => setViewingWebsiteJob(null)}
        onEdit={(instructions) => viewingWebsiteJob && handleWebsiteEdit(viewingWebsiteJob, instructions)}
        isGenerating={isGeneratingWebsite}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
