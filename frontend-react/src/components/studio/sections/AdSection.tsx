/**
 * AdSection Component
 * Educational Note: Self-contained section for ad creative generation.
 * Note: Ads use studio_item signal check instead of source_id filtering.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext } from '../StudioContext';
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
        <AdProgressIndicator currentAdJob={currentAdJob} />
      )}

      {hasAdSignal && savedAdJobs.map((job) => (
        <AdListItem
          key={job.id}
          job={job}
          onClick={() => setViewingAdJob(job)}
        />
      ))}

      <AdViewerModal
        viewingAdJob={viewingAdJob}
        onClose={() => setViewingAdJob(null)}
      />
    </>
  );
};
