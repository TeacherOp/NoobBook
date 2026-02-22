/**
 * useWebsiteGeneration Hook
 * Educational Note: Custom hook for website generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState } from 'react';
import { websitesAPI, type WebsiteJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('website-generation');

export const useWebsiteGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedWebsiteJobs, setSavedWebsiteJobs] = useState<WebsiteJob[]>([]);
  const [currentWebsiteJob, setCurrentWebsiteJob] = useState<WebsiteJob | null>(null);
  const [isGeneratingWebsite, setIsGeneratingWebsite] = useState(false);
  const [viewingWebsiteJob, setViewingWebsiteJob] = useState<WebsiteJob | null>(null);

  /**
   * Load saved website jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const websiteResponse = await websitesAPI.listJobs(projectId);
      if (websiteResponse.success && websiteResponse.jobs) {
        const completedWebsites = websiteResponse.jobs.filter((job) => job.status === 'ready');
        setSavedWebsiteJobs(completedWebsites);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved website jobs');
    }
  };

  /**
   * Handle website generation
   * Educational Note: Websites open in new window automatically after generation
   */
  const handleWebsiteGeneration = async (signal: StudioSignal) => {
    setIsGeneratingWebsite(true);
    setCurrentWebsiteJob(null);

    try {
      const sourceId = signal.sources[0]?.source_id;
      if (!sourceId) {
        showError('No source selected');
        return;
      }

      // Start website generation
      const startResponse = await websitesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start website generation');
        return;
      }

      // Poll for completion
      const finalJob = await websitesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentWebsiteJob(job)
      );

      if (finalJob.status === 'ready') {
        setSavedWebsiteJobs((prev) => [finalJob, ...prev]);
        // Open website in modal viewer automatically
        setViewingWebsiteJob(finalJob);
        showSuccess('Website generated successfully!');
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Website generation failed');
      }
    } catch (error) {
      log.error({ err: error }, 'LWebsite generationE failed');
      showError('Website generation failed');
    } finally {
      setIsGeneratingWebsite(false);
      setCurrentWebsiteJob(null);
    }
  };

  /**
   * Open website in modal viewer
   */
  const openWebsite = (jobId: string) => {
    const job = savedWebsiteJobs.find((j) => j.id === jobId);
    if (job) {
      setViewingWebsiteJob(job);
    }
  };

  /**
   * Download website as ZIP
   */
  const downloadWebsite = (jobId: string) => {
    const downloadUrl = websitesAPI.getDownloadUrl(projectId, jobId);
    const link = document.createElement('a');
    link.href = getAuthUrl(downloadUrl);
    link.click();
  };

  return {
    savedWebsiteJobs,
    currentWebsiteJob,
    isGeneratingWebsite,
    viewingWebsiteJob,
    setViewingWebsiteJob,
    loadSavedJobs,
    handleWebsiteGeneration,
    openWebsite,
    downloadWebsite,
  };
};
