/**
 * usePRDGeneration Hook
 * Educational Note: Manages PRD (Product Requirements Document) generation.
 * PRDs are created incrementally by the agent and stored as markdown files.
 */

import { useState, useRef } from 'react';
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
  const pollingRef = useRef(false);
  const [viewingPRDJob, setViewingPRDJob] = useState<PRDJob | null>(null);

  const loadSavedJobs = async () => {
    try {
      const prdResponse = await prdsAPI.listJobs(projectId);
      if (prdResponse.success && prdResponse.jobs) {
        const finishedJobs = prdResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedPRDJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingPRD && !pollingRef.current) {
          const inProgressJob = prdResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingPRD(true);
            setCurrentPRDJob(inProgressJob);
            try {
              const finalJob = await prdsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentPRDJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                setSavedPRDJobs((prev) => [finalJob, ...prev]);
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingPRD(false);
              setCurrentPRDJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved PRD jobs');
    }
  };

  const handlePRDEdit = async (parentJob: PRDJob, editInstructions: string) => {
    setIsGeneratingPRD(true);
    setCurrentPRDJob(null);

    try {
      const startResponse = await prdsAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,
        editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start PRD edit.');
        setIsGeneratingPRD(false);
        return;
      }

      // Close modal only after edit confirmed started
      setViewingPRDJob(null);
      showSuccess('Editing PRD document...');

      const finalJob = await prdsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentPRDJob(job)
      );

      setCurrentPRDJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`PRD updated: ${finalJob.document_title || 'PRD'}`);
        setSavedPRDJobs((prev) => [finalJob, ...prev]);
        setViewingPRDJob(finalJob);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'PRD edit failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'PRD edit failed');
      showError(error instanceof Error ? error.message : 'PRD edit failed.');
    } finally {
      setIsGeneratingPRD(false);
      setCurrentPRDJob(null);
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
    handlePRDEdit,
    downloadPRD,
  };
};
