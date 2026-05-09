/**
 * AdSection Component
 * Educational Note: Self-contained section for ad creative generation.
 * Note: Ads use studio_item signal check instead of source_id filtering.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext } from '../studio-hooks';
import { useAdGeneration } from '../ads/useAdGeneration';
import { AdListItem } from '../ads/AdListItem';
import { AdProgressIndicator } from '../ads/AdProgressIndicator';
import { AdViewerModal } from '../ads/AdViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const AdSection: React.FC = () => {
  const { projectId, signals, registerGenerationHandler } = useStudioContext();

  const {
    savedAdJobs,
    currentAdJob,
    isGeneratingAd,
    viewingAdJob,
    setViewingAdJob,
    configError,
    loadSavedJobs,
    handleAdGeneration,
    handleAdEdit,
    handleAdDelete,
  } = useAdGeneration(projectId);

  // Ads show if any ads_creative signal exists (not filtered by source_id)
  const hasAdSignal = signals.some((s) => s.studio_item === 'ads_creative');

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleAdGeneration>[0]) => {
    await handleAdGeneration(signal);
  }, [handleAdGeneration]);

  useEffect(() => {
    registerGenerationHandler('ads_creative', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  // Only show if we have ad signal and jobs, or generating, or config error
  if (!hasAdSignal && savedAdJobs.length === 0 && !isGeneratingAd && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingAd && (
        <AdProgressIndicator currentAdJob={currentAdJob} projectId={projectId} />
      )}

      {hasAdSignal && savedAdJobs.map((job, i) => (
        <AdListItem
          key={job.id}
          job={job}
          iterationIndex={savedAdJobs.length - i}
          onClick={() => setViewingAdJob(job)}
          onDelete={() => handleAdDelete(job.id)}
        />
      ))}

      <AdViewerModal
        viewingAdJob={viewingAdJob}
        onClose={() => setViewingAdJob(null)}
        onEdit={(instructions) => viewingAdJob && handleAdEdit(viewingAdJob, instructions)}
      />
    </>
  );
};
