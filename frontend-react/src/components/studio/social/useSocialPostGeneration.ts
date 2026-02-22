/**
 * useSocialPostGeneration Hook
 * Educational Note: Custom hook for social post generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState, useRef } from 'react';
import { socialPostsAPI, checkGeminiStatus, type SocialPostJob } from '@/lib/api/studio';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('social-post-generation');

export const useSocialPostGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedSocialPostJobs, setSavedSocialPostJobs] = useState<SocialPostJob[]>([]);
  const [currentSocialPostJob, setCurrentSocialPostJob] = useState<SocialPostJob | null>(null);
  const [isGeneratingSocialPosts, setIsGeneratingSocialPosts] = useState(false);
  const [viewingSocialPostJob, setViewingSocialPostJob] = useState<SocialPostJob | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Load saved social post jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const socialPostResponse = await socialPostsAPI.listJobs(projectId);
      if (socialPostResponse.success && socialPostResponse.jobs) {
        const completedSocialPosts = socialPostResponse.jobs.filter((job) => job.status === 'ready');
        setSavedSocialPostJobs(completedSocialPosts);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved social post jobs');
    }
  };

  /**
   * Handle social post generation
   */
  const handleSocialPostGeneration = async (signal: StudioSignal) => {
    // Extract topic from direction
    const topic = signal.direction || 'Topic';

    setIsGeneratingSocialPosts(true);
    setCurrentSocialPostJob(null);

    try {
      const geminiStatus = await checkGeminiStatus();
      if (!geminiStatus.configured) {
        // Show inline banner so the user clearly sees what's missing
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError('Add your Gemini API key in Admin Settings to generate social posts with images.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        setIsGeneratingSocialPosts(false);
        return;
      }

      const startResponse = await socialPostsAPI.startGeneration(
        projectId,
        topic,
        signal.direction,
        ['linkedin', 'instagram', 'twitter']
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start social post generation.');
        setIsGeneratingSocialPosts(false);
        return;
      }

      showSuccess(`Generating social posts...`);

      const finalJob = await socialPostsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentSocialPostJob(job)
      );

      setCurrentSocialPostJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.post_count} social posts!`);
        setSavedSocialPostJobs((prev) => [finalJob, ...prev]);
        setViewingSocialPostJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Social post generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LSocial post generationE failed');
      showError(error instanceof Error ? error.message : 'Social post generation failed.');
    } finally {
      setIsGeneratingSocialPosts(false);
      setCurrentSocialPostJob(null);
    }
  };

  return {
    savedSocialPostJobs,
    currentSocialPostJob,
    isGeneratingSocialPosts,
    viewingSocialPostJob,
    setViewingSocialPostJob,
    configError,
    loadSavedJobs,
    handleSocialPostGeneration,
  };
};
