/**
 * MarketingStrategySection Component
 * Educational Note: Self-contained section for marketing strategy generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useMarketingStrategyGeneration } from '../marketingStrategy/useMarketingStrategyGeneration';
import { MarketingStrategyListItem } from '../marketingStrategy/MarketingStrategyListItem';
import { MarketingStrategyProgressIndicator } from '../marketingStrategy/MarketingStrategyProgressIndicator';
import { MarketingStrategyViewerModal } from '../marketingStrategy/MarketingStrategyViewerModal';

export const MarketingStrategySection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedMarketingStrategyJobs,
    currentMarketingStrategyJob,
    isGeneratingMarketingStrategy,
    viewingMarketingStrategyJob,
    setViewingMarketingStrategyJob,
    loadSavedJobs,
    handleMarketingStrategyGeneration,
    downloadMarketingStrategy,
  } = useMarketingStrategyGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedMarketingStrategyJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleMarketingStrategyGeneration>[0]) => {
    await handleMarketingStrategyGeneration(signal);
  }, [handleMarketingStrategyGeneration]);

  useEffect(() => {
    registerGenerationHandler('marketing_strategy', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingMarketingStrategy) {
    return null;
  }

  return (
    <>
      {isGeneratingMarketingStrategy && (
        <MarketingStrategyProgressIndicator currentMarketingStrategyJob={currentMarketingStrategyJob} />
      )}

      {filteredJobs.map((job) => (
        <MarketingStrategyListItem
          key={job.id}
          job={job}
          onOpen={() => setViewingMarketingStrategyJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadMarketingStrategy(job.id);
          }}
        />
      ))}

      <MarketingStrategyViewerModal
        projectId={projectId}
        viewingMarketingStrategyJob={viewingMarketingStrategyJob}
        onClose={() => setViewingMarketingStrategyJob(null)}
        onDownload={downloadMarketingStrategy}
      />
    </>
  );
};
