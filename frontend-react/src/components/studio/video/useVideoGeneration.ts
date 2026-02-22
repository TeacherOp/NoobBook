/**
 * useVideoGeneration Hook
 * Educational Note: Custom hook for video generation logic using Google Veo 2.0.
 * Handles state management, API calls, and polling for video generation jobs.
 * Videos are generated in two steps: Claude creates optimized prompt -> Google Veo generates video.
 */

import { useState } from 'react';
import { videosAPI, type VideoJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('video-generation');

export const useVideoGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedVideoJobs, setSavedVideoJobs] = useState<VideoJob[]>([]);
  const [currentVideoJob, setCurrentVideoJob] = useState<VideoJob | null>(null);
  const [isGeneratingVideo, setIsGeneratingVideo] = useState(false);
  const [viewingVideoJob, setViewingVideoJob] = useState<VideoJob | null>(null);

  /**
   * Load saved video jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const videoResponse = await videosAPI.listJobs(projectId);
      if (videoResponse.success && videoResponse.jobs) {
        const completedVideos = videoResponse.jobs.filter((job) => job.status === 'ready');
        setSavedVideoJobs(completedVideos);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved video jobs');
    }
  };

  /**
   * Handle video generation
   * Educational Note: Videos can take 10-20 minutes to generate with Google Veo
   * Default parameters: 16:9 aspect ratio, 8 seconds duration, 1 video
   */
  const handleVideoGeneration = async (
    signal: StudioSignal,
    aspectRatio: '16:9' | '16:10' = '16:9',
    durationSeconds: number = 8,
    numberOfVideos: number = 1
  ) => {
    setIsGeneratingVideo(true);
    setCurrentVideoJob(null);

    try {
      const sourceId = signal.sources[0]?.source_id;
      if (!sourceId) {
        showError('No source selected');
        return;
      }

      // Start video generation
      const startResponse = await videosAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction,
        aspectRatio,
        durationSeconds,
        numberOfVideos
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start video generation');
        return;
      }

      // Poll for completion (can take 10-20 minutes)
      const finalJob = await videosAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentVideoJob(job)
      );

      if (finalJob.status === 'ready') {
        setSavedVideoJobs((prev) => [finalJob, ...prev]);
        // Open video in modal viewer automatically
        setViewingVideoJob(finalJob);
        showSuccess(`Generated ${finalJob.videos.length} video(s) successfully!`);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Video generation failed');
      }
    } catch (error) {
      log.error({ err: error }, 'LVideo generationE failed');
      showError('Video generation failed');
    } finally {
      setIsGeneratingVideo(false);
      setCurrentVideoJob(null);
    }
  };

  /**
   * Open video in modal viewer
   */
  const openVideo = (jobId: string) => {
    const job = savedVideoJobs.find((j) => j.id === jobId);
    if (job) {
      setViewingVideoJob(job);
    }
  };

  /**
   * Download video file
   */
  const downloadVideo = (jobId: string, filename: string) => {
    const downloadUrl = videosAPI.getDownloadUrl(projectId, jobId, filename);
    const link = document.createElement('a');
    link.href = getAuthUrl(downloadUrl);
    link.download = filename;
    link.click();
  };

  return {
    savedVideoJobs,
    currentVideoJob,
    isGeneratingVideo,
    viewingVideoJob,
    setViewingVideoJob,
    loadSavedJobs,
    handleVideoGeneration,
    openVideo,
    downloadVideo,
  };
};
