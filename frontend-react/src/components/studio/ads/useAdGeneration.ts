/**
 * useAdGeneration Hook
 * Educational Note: Custom hook for ad creative generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState, useRef } from 'react';
import { adsAPI, checkGeminiStatus, type AdJob } from '@/lib/api/studio';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('ad-generation');

export const useAdGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedAdJobs, setSavedAdJobs] = useState<AdJob[]>([]);
  const [currentAdJob, setCurrentAdJob] = useState<AdJob | null>(null);
  const [isGeneratingAd, setIsGeneratingAd] = useState(false);
  const [viewingAdJob, setViewingAdJob] = useState<AdJob | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Load saved ad jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const adResponse = await adsAPI.listJobs(projectId);
      if (adResponse.success && adResponse.jobs) {
        const completedAds = adResponse.jobs.filter((job) => job.status === 'ready');
        setSavedAdJobs(completedAds);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved ad jobs');
    }
  };

  /**
   * Handle ad creative generation
   */
  const handleAdGeneration = async (signal: StudioSignal) => {
    // Extract product name from direction
    const productName = signal.direction || 'Product';

    setIsGeneratingAd(true);
    setCurrentAdJob(null);

    try {
      const geminiStatus = await checkGeminiStatus();
      if (!geminiStatus.configured) {
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError('Add your Gemini API key in Admin Settings to generate ad creatives with images.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        setIsGeneratingAd(false);
        return;
      }

      const startResponse = await adsAPI.startGeneration(
        projectId,
        productName,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start ad generation.');
        setIsGeneratingAd(false);
        return;
      }

      showSuccess(`Generating ad creatives...`);

      const finalJob = await adsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentAdJob(job)
      );

      setCurrentAdJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.images.length} ad creatives!`);
        setSavedAdJobs((prev) => [finalJob, ...prev]);
        setViewingAdJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Ad generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LAd generationE failed');
      showError(error instanceof Error ? error.message : 'Ad generation failed.');
    } finally {
      setIsGeneratingAd(false);
      setCurrentAdJob(null);
    }
  };

  return {
    savedAdJobs,
    currentAdJob,
    isGeneratingAd,
    viewingAdJob,
    setViewingAdJob,
    configError,
    loadSavedJobs,
    handleAdGeneration,
  };
};
