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

  const {
    savedAudioJobs,
    currentAudioJob,
    isGeneratingAudio,
    playingJobId,
    isPaused,
    currentTime,
    duration,
    audioRef,
    handleAudioEnd,
    handleTimeUpdate,
    handleLoadedMetadata,
    loadSavedJobs,
    handleAudioGeneration,
    playAudio,
    pauseAudio,
    seekTo,
    playbackRate,
    cyclePlaybackRate,
    downloadAudio,
    formatDuration,
  } = useAudioGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedAudioJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleAudioGeneration>[0]) => {
    await handleAudioGeneration(signal);
  }, [handleAudioGeneration]);

  useEffect(() => {
    registerGenerationHandler('audio_overview', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingAudio) {
    return null;
  }

  return (
    <>
      <audio
        ref={audioRef}
        onEnded={handleAudioEnd}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        className="hidden"
      />

      {isGeneratingAudio && (
        <AudioProgressIndicator currentAudioJob={currentAudioJob} />
      )}

      {filteredJobs.map((job) => (
        <AudioListItem
          key={job.id}
          job={job}
          playingJobId={playingJobId}
          isPaused={isPaused}
          currentTime={currentTime}
          duration={duration}
          onPlay={playAudio}
          onPause={pauseAudio}
          onSeek={seekTo}
          playbackRate={playbackRate}
          onCycleSpeed={cyclePlaybackRate}
          onDownload={downloadAudio}
          formatDuration={formatDuration}
        />
      ))}
    </>
  );
};
