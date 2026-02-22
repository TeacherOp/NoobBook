/**
 * SocialSection Component
 * Educational Note: Self-contained section for social post generation.
 * Note: Social posts use studio_item signal check instead of source_id filtering.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext } from '../StudioContext';
import { useSocialPostGeneration } from '../social/useSocialPostGeneration';
import { SocialPostListItem } from '../social/SocialPostListItem';
import { SocialPostProgressIndicator } from '../social/SocialPostProgressIndicator';
import { SocialPostViewerModal } from '../social/SocialPostViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const SocialSection: React.FC = () => {
  const { projectId, signals, registerGenerationHandler } = useStudioContext();

  const {
    savedSocialPostJobs,
    currentSocialPostJob,
    isGeneratingSocialPosts,
    viewingSocialPostJob,
    setViewingSocialPostJob,
    configError,
    loadSavedJobs,
    handleSocialPostGeneration,
  } = useSocialPostGeneration(projectId);

  const hasSocialSignal = signals.some((s) => s.studio_item === 'social');

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleSocialPostGeneration>[0]) => {
    await handleSocialPostGeneration(signal);
  }, [handleSocialPostGeneration]);

  useEffect(() => {
    registerGenerationHandler('social', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (!hasSocialSignal && savedSocialPostJobs.length === 0 && !isGeneratingSocialPosts && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingSocialPosts && (
        <SocialPostProgressIndicator currentSocialPostJob={currentSocialPostJob} />
      )}

      {hasSocialSignal && savedSocialPostJobs.map((job) => (
        <SocialPostListItem
          key={job.id}
          job={job}
          onClick={() => setViewingSocialPostJob(job)}
        />
      ))}

      <SocialPostViewerModal
        viewingSocialPostJob={viewingSocialPostJob}
        onClose={() => setViewingSocialPostJob(null)}
      />
    </>
  );
};
