/**
 * AudioSection Component
 * Educational Note: Self-contained section for audio generation.
 * Owns all audio-related state via useAudioGeneration hook.
 * Only re-renders when audio state changes - isolated from other sections.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useAudioGeneration } from '../audio/useAudioGeneration';
import { AudioListItem } from '../audio/AudioListItem';
import { AudioProgressIndicator } from '../audio/AudioProgressIndicator';

export const AudioSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  // All audio state is owned here - not in parent
  const {
    savedAudioJobs,
    currentAudioJob,
    isGeneratingAudio,
    playingJobId,
    audioRef,
    handleAudioEnd,
    loadSavedJobs,
    handleAudioGeneration,
    playAudio,
    pauseAudio,
    downloadAudio,
  } = useAudioGeneration(projectId);

  // Filter jobs by valid source IDs using O(1) Set lookup
  const filteredJobs = useFilteredJobs(savedAudioJobs);

  // Load saved jobs on mount
  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Register generation handler with context
  const handleGenerate = useCallback(async (signal: Parameters<typeof handleAudioGeneration>[0]) => {
    await handleAudioGeneration(signal);
  }, [handleAudioGeneration]);

  useEffect(() => {
    registerGenerationHandler('audio_overview', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  // Don't render anything if no jobs and not generating
  if (filteredJobs.length === 0 && !isGeneratingAudio) {
    return null;
  }

  return (
    <>
      {/* Hidden audio element for playback */}
      <audio
        ref={audioRef}
        onEnded={handleAudioEnd}
        className="hidden"
      />

      {/* Progress indicator when generating */}
      {isGeneratingAudio && (
        <AudioProgressIndicator currentAudioJob={currentAudioJob} />
      )}

      {/* List of saved audio jobs */}
      {filteredJobs.map((job) => (
        <AudioListItem
          key={job.id}
          job={job}
          playingJobId={playingJobId}
          onPlay={playAudio}
          onPause={pauseAudio}
          onDownload={downloadAudio}
        />
      ))}
    </>
  );
};
