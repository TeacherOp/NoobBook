/**
 * useMarketingStrategyGeneration Hook
 * Educational Note: Manages Marketing Strategy document generation.
 * Marketing strategies are created incrementally by the agent and stored as markdown files.
 */

import { useState, useRef } from 'react';
import { marketingStrategiesAPI, type MarketingStrategyJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('marketing-strategy-generation');

export const useMarketingStrategyGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedMarketingStrategyJobs, setSavedMarketingStrategyJobs] = useState<MarketingStrategyJob[]>([]);
  const [currentMarketingStrategyJob, setCurrentMarketingStrategyJob] = useState<MarketingStrategyJob | null>(null);
  const [isGeneratingMarketingStrategy, setIsGeneratingMarketingStrategy] = useState(false);
  const pollingRef = useRef(false);
  const [viewingMarketingStrategyJob, setViewingMarketingStrategyJob] = useState<MarketingStrategyJob | null>(null);

  const loadSavedJobs = async () => {
    try {
      const response = await marketingStrategiesAPI.listJobs(projectId);
      if (response.success && response.jobs) {
        const finishedJobs = response.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedMarketingStrategyJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingMarketingStrategy && !pollingRef.current) {
          const inProgressJob = response.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingMarketingStrategy(true);
            setCurrentMarketingStrategyJob(inProgressJob);
            try {
              const finalJob = await marketingStrategiesAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentMarketingStrategyJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                setSavedMarketingStrategyJobs((prev) => [finalJob, ...prev]);
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingMarketingStrategy(false);
              setCurrentMarketingStrategyJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved marketing strategy jobs');
    }
  };

  const handleMarketingStrategyEdit = async (parentJob: MarketingStrategyJob, editInstructions: string) => {
    setIsGeneratingMarketingStrategy(true);
    setCurrentMarketingStrategyJob(null);

    try {
      const startResponse = await marketingStrategiesAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,
        editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start marketing strategy edit.');
        setIsGeneratingMarketingStrategy(false);
        return;
      }

      // Close modal only after edit confirmed started
      setViewingMarketingStrategyJob(null);
      showSuccess('Editing marketing strategy...');

      const finalJob = await marketingStrategiesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentMarketingStrategyJob(job)
      );

      setCurrentMarketingStrategyJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Marketing strategy updated: ${finalJob.document_title || 'Marketing Strategy'}`);
        setSavedMarketingStrategyJobs((prev) => [finalJob, ...prev]);
        setViewingMarketingStrategyJob(finalJob);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Marketing strategy edit failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'marketing strategy edit failed');
      showError(error instanceof Error ? error.message : 'Marketing strategy edit failed.');
    } finally {
      setIsGeneratingMarketingStrategy(false);
      setCurrentMarketingStrategyJob(null);
    }
  };

  const handleMarketingStrategyGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for marketing strategy generation.');
      return;
    }

    setIsGeneratingMarketingStrategy(true);
    setCurrentMarketingStrategyJob(null);

    try {
      const startResponse = await marketingStrategiesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start marketing strategy generation.');
        setIsGeneratingMarketingStrategy(false);
        return;
      }

      showSuccess('Generating marketing strategy document...');

      const finalJob = await marketingStrategiesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentMarketingStrategyJob(job)
      );

      setCurrentMarketingStrategyJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Marketing strategy generated: ${finalJob.document_title || 'Marketing Strategy Document'}`);
        setSavedMarketingStrategyJobs((prev) => [finalJob, ...prev]);
        setViewingMarketingStrategyJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Marketing strategy generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LMarketing strategy generationE failed');
      showError(error instanceof Error ? error.message : 'Marketing strategy generation failed.');
    } finally {
      setIsGeneratingMarketingStrategy(false);
      setCurrentMarketingStrategyJob(null);
    }
  };

  const downloadMarketingStrategy = (jobId: string) => {
    const url = marketingStrategiesAPI.getDownloadUrl(projectId, jobId);
    window.open(getAuthUrl(url), '_blank');
  };

  return {
    savedMarketingStrategyJobs,
    currentMarketingStrategyJob,
    isGeneratingMarketingStrategy,
    viewingMarketingStrategyJob,
    setViewingMarketingStrategyJob,
    loadSavedJobs,
    handleMarketingStrategyGeneration,
    handleMarketingStrategyEdit,
    downloadMarketingStrategy,
  };
};
