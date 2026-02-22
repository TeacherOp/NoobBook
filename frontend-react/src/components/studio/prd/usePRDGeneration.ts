/**
 * usePRDGeneration Hook
 * Educational Note: Manages PRD (Product Requirements Document) generation.
 * PRDs are created incrementally by the agent and stored as markdown files.
 */

import { useState } from 'react';
import { prdsAPI, type PRDJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('prd-generation');

export const usePRDGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedPRDJobs, setSavedPRDJobs] = useState<PRDJob[]>([]);
  const [currentPRDJob, setCurrentPRDJob] = useState<PRDJob | null>(null);
  const [isGeneratingPRD, setIsGeneratingPRD] = useState(false);
  const [viewingPRDJob, setViewingPRDJob] = useState<PRDJob | null>(null);

  const loadSavedJobs = async () => {
    const prdResponse = await prdsAPI.listJobs(projectId);
    if (prdResponse.success && prdResponse.jobs) {
      const completedPRDs = prdResponse.jobs.filter((job) => job.status === 'ready');
      setSavedPRDJobs(completedPRDs);
    }
  };

  const handlePRDGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for PRD generation.');
      return;
    }

    setIsGeneratingPRD(true);
    setCurrentPRDJob(null);

    try {
      const startResponse = await prdsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start PRD generation.');
        setIsGeneratingPRD(false);
        return;
      }

      showSuccess('Generating PRD document...');

      const finalJob = await prdsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentPRDJob(job)
      );

      setCurrentPRDJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`PRD generated: ${finalJob.document_title || 'Product Requirements Document'}`);
        setSavedPRDJobs((prev) => [finalJob, ...prev]);
        setViewingPRDJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'PRD generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LPRD generationE failed');
      showError(error instanceof Error ? error.message : 'PRD generation failed.');
    } finally {
      setIsGeneratingPRD(false);
      setCurrentPRDJob(null);
    }
  };

  const downloadPRD = (jobId: string) => {
    const url = prdsAPI.getDownloadUrl(projectId, jobId);
    window.open(getAuthUrl(url), '_blank');
  };

  return {
    savedPRDJobs,
    currentPRDJob,
    isGeneratingPRD,
    viewingPRDJob,
    setViewingPRDJob,
    loadSavedJobs,
    handlePRDGeneration,
    downloadPRD,
  };
};
