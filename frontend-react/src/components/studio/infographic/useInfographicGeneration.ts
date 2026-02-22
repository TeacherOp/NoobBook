/**
 * useInfographicGeneration Hook
 * Educational Note: Custom hook for infographic generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState, useRef } from 'react';
import { infographicsAPI, checkGeminiStatus, type InfographicJob } from '@/lib/api/studio';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('infographic-generation');

export const useInfographicGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedInfographicJobs, setSavedInfographicJobs] = useState<InfographicJob[]>([]);
  const [currentInfographicJob, setCurrentInfographicJob] = useState<InfographicJob | null>(null);
  const [isGeneratingInfographic, setIsGeneratingInfographic] = useState(false);
  const [viewingInfographicJob, setViewingInfographicJob] = useState<InfographicJob | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Load saved infographic jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const infographicResponse = await infographicsAPI.listJobs(projectId);
      if (infographicResponse.success && infographicResponse.jobs) {
        const completedInfographics = infographicResponse.jobs.filter((job) => job.status === 'ready');
        setSavedInfographicJobs(completedInfographics);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved infographic jobs');
    }
  };

  /**
   * Handle infographic generation
   */
  const handleInfographicGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for infographic generation.');
      return;
    }

    setIsGeneratingInfographic(true);
    setCurrentInfographicJob(null);

    try {
      const geminiStatus = await checkGeminiStatus();
      if (!geminiStatus.configured) {
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError('Add your Gemini API key in Admin Settings to generate infographics with images.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        setIsGeneratingInfographic(false);
        return;
      }

      const startResponse = await infographicsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start infographic generation.');
        setIsGeneratingInfographic(false);
        return;
      }

      showSuccess(`Generating infographic for ${startResponse.source_name}...`);

      const finalJob = await infographicsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentInfographicJob(job)
      );

      setCurrentInfographicJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated infographic: ${finalJob.topic_title}!`);
        setSavedInfographicJobs((prev) => [finalJob, ...prev]);
        setViewingInfographicJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Infographic generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LInfographic generationE failed');
      showError(error instanceof Error ? error.message : 'Infographic generation failed.');
    } finally {
      setIsGeneratingInfographic(false);
      setCurrentInfographicJob(null);
    }
  };

  return {
    savedInfographicJobs,
    currentInfographicJob,
    isGeneratingInfographic,
    viewingInfographicJob,
    setViewingInfographicJob,
    configError,
    loadSavedJobs,
    handleInfographicGeneration,
  };
};
