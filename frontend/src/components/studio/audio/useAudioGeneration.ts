/**
 * useAudioGeneration Hook
 * Educational Note: Manages audio overview generation with ElevenLabs TTS.
 * Includes playback state management with a shared audio element.
 */

import { useState, useRef } from 'react';
import { audioAPI, type AudioJob } from '@/lib/api/studio';
import { API_HOST } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';

export const useAudioGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedAudioJobs, setSavedAudioJobs] = useState<AudioJob[]>([]);
  const [currentAudioJob, setCurrentAudioJob] = useState<AudioJob | null>(null);
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [playingJobId, setPlayingJobId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const loadSavedJobs = async () => {
    const audioResponse = await audioAPI.listJobs(projectId);
    if (audioResponse.success && audioResponse.jobs) {
      const completedAudio = audioResponse.jobs.filter((job) => job.status === 'ready');
      setSavedAudioJobs(completedAudio);
    }
  };

  const handleAudioGeneration = async (signal: StudioSignal) => {
    console.log('[useAudioGeneration] handleAudioGeneration called with signal:', signal);
    const sourceId = signal.sources[0]?.source_id;
    console.log('[useAudioGeneration] Extracted sourceId:', sourceId);
    if (!sourceId) {
      console.error('[useAudioGeneration] No source_id found in signal.sources:', signal.sources);
      showError('No source specified for audio generation.');
      return;
    }

    setIsGeneratingAudio(true);
    setCurrentAudioJob(null);

    try {
      const ttsStatus = await audioAPI.checkTTSStatus();
      if (!ttsStatus.configured) {
        showError('ElevenLabs API key not configured. Please add it in App Settings.');
        setIsGeneratingAudio(false);
        return;
      }

      const startResponse = await audioAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start audio generation.');
        setIsGeneratingAudio(false);
        return;
      }

      showSuccess(`Generating audio for ${startResponse.source_name}...`);

      const finalJob = await audioAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentAudioJob(job)
      );

      setCurrentAudioJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess('Your audio overview is ready to play!');
        setSavedAudioJobs((prev) => [finalJob, ...prev]);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Audio generation failed.');
      }
    } catch (error) {
      console.error('Audio generation error:', error);
      showError(error instanceof Error ? error.message : 'Audio generation failed.');
    } finally {
      setIsGeneratingAudio(false);
      setCurrentAudioJob(null);
    }
  };

  /**
   * Play a specific audio job
   */
  const playAudio = (job: AudioJob) => {
    if (!job.audio_url) return;

    // Stop current playback if different job
    if (audioRef.current && playingJobId !== job.id) {
      audioRef.current.pause();
    }

    // Set the source and play
    if (audioRef.current) {
      audioRef.current.src = `${API_HOST}${job.audio_url}`;
      audioRef.current.play();
      setPlayingJobId(job.id);
    }
  };

  /**
   * Pause current playback
   */
  const pauseAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    setPlayingJobId(null);
  };

  /**
   * Handle audio end
   */
  const handleAudioEnd = () => {
    setPlayingJobId(null);
  };

  /**
   * Download audio file
   * Educational Note: Cross-origin downloads require fetching as blob first.
   * The `download` attribute on anchor tags only works for same-origin URLs.
   */
  const downloadAudio = async (job: AudioJob) => {
    if (!job.audio_url) return;

    try {
      const response = await fetch(`${API_HOST}${job.audio_url}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = job.audio_filename || 'audio_overview.mp3';
      link.click();

      // Clean up the object URL after download
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download audio:', error);
      showError('Failed to download audio file');
    }
  };

  /**
   * Format duration for display
   */
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return {
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
    formatDuration,
  };
};
