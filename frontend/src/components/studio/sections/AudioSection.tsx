/**
 * AudioSection Component
 * Educational Note: Self-contained section for audio generation.
 * Owns all audio-related state via useAudioGeneration hook.
 * Only re-renders when audio state changes - isolated from other sections.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
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
    handleAudioEdit,
    handleAudioDelete,
    playAudio,
    pauseAudio,
    seekTo,
    playbackRate,
    cyclePlaybackRate,
    downloadAudio,
    formatDuration,
    editingJobId,
    pendingEditInput,
  } = useAudioGeneration(projectId);

  // Track which item has its edit input open — only one at a time
  const [openEditJobId, setOpenEditJobId] = useState<string | null>(null);

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
        <AudioProgressIndicator currentAudioJob={currentAudioJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <AudioListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
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
          onEdit={handleAudioEdit}
          isEditing={editingJobId === job.id}
          isGenerating={isGeneratingAudio}
          defaultEditInput={editingJobId === job.id ? pendingEditInput : ''}
          isEditOpen={openEditJobId === job.id || editingJobId === job.id}
          onToggleEdit={() => setOpenEditJobId(prev => prev === job.id ? null : job.id)}
          onDelete={() => handleAudioDelete(job.id)}
        />
      ))}
    </>
  );
};
