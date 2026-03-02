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
  const pollingRef = useRef(false);
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
        const finishedJobs = adResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedAdJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingAd && !pollingRef.current) {
          const inProgressJob = adResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingAd(true);
            setCurrentAdJob(inProgressJob);
            try {
              const finalJob = await adsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentAdJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                setSavedAdJobs((prev) => [finalJob, ...prev]);
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingAd(false);
              setCurrentAdJob(null);
            }
          }
        }
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

      // Logo source defaults to 'auto' — backend auto-detects brand icon/logo
      const startResponse = await adsAPI.startGeneration(
        projectId,
        productName,
        signal.direction,
        'auto'
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

  /**
   * Handle editing an existing ad job — creates a new job with previous prompts as context
   */
  const handleAdEdit = async (parentJob: AdJob, editInstructions: string) => {
    setIsGeneratingAd(true);
    setCurrentAdJob(null);
    setViewingAdJob(null);

    try {
      const geminiStatus = await checkGeminiStatus();
      if (!geminiStatus.configured) {
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError('Add your Gemini API key in Admin Settings to edit ad creatives.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        setIsGeneratingAd(false);
        return;
      }

      const startResponse = await adsAPI.startGeneration(
        projectId,
        parentJob.product_name,
        parentJob.direction,
        'auto',
        undefined,
        parentJob.id,
        editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start ad edit.');
        setIsGeneratingAd(false);
        return;
      }

      showSuccess('Editing ad creatives...');

      const finalJob = await adsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentAdJob(job)
      );

      setCurrentAdJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.images.length} edited ad creatives!`);
        setSavedAdJobs((prev) => [finalJob, ...prev]);
        setViewingAdJob(finalJob);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Ad edit failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'ad edit failed');
      showError(error instanceof Error ? error.message : 'Ad edit failed.');
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
    handleAdEdit,
  };
};
