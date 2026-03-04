/**
 * useComponentGeneration Hook
 * Educational Note: Custom hook for UI component generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState, useRef } from 'react';
import { componentsAPI, type ComponentJob } from '@/lib/api/studio';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('component-generation');

export const useComponentGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedComponentJobs, setSavedComponentJobs] = useState<ComponentJob[]>([]);
  const [currentComponentJob, setCurrentComponentJob] = useState<ComponentJob | null>(null);
  const [isGeneratingComponents, setIsGeneratingComponents] = useState(false);
  const pollingRef = useRef(false);
  const [viewingComponentJob, setViewingComponentJob] = useState<ComponentJob | null>(null);

  /**
   * Load saved component jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const componentResponse = await componentsAPI.listJobs(projectId);
      if (componentResponse.success && componentResponse.jobs) {
        const finishedJobs = componentResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedComponentJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingComponents && !pollingRef.current) {
          const inProgressJob = componentResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingComponents(true);
            setCurrentComponentJob(inProgressJob);
            try {
              const finalJob = await componentsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentComponentJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                setSavedComponentJobs((prev) => [finalJob, ...prev]);
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingComponents(false);
              setCurrentComponentJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved component jobs');
    }
  };

  /**
   * Handle component generation
   */
  const handleComponentGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for component generation.');
      return;
    }

    setIsGeneratingComponents(true);
    setCurrentComponentJob(null);

    try {
      const startResponse = await componentsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start component generation.');
        setIsGeneratingComponents(false);
        return;
      }

      showSuccess(`Generating components...`);

      const finalJob = await componentsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentComponentJob(job)
      );

      setCurrentComponentJob(finalJob);

      if (finalJob.status === 'ready') {
        const componentCount = finalJob.components?.length || 0;
        showSuccess(`Generated ${componentCount} component variation${componentCount !== 1 ? 's' : ''}!`);
        setSavedComponentJobs((prev) => [finalJob, ...prev]);
        setViewingComponentJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Component generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LComponent generationE failed');
      showError(error instanceof Error ? error.message : 'Component generation failed.');
    } finally {
      setIsGeneratingComponents(false);
      setCurrentComponentJob(null);
    }
  };

  /**
   * Handle component edit — creates a new job with previous context
   */
  const handleComponentEdit = async (parentJob: ComponentJob, editInstructions: string) => {
    setIsGeneratingComponents(true);

    try {
      const startResponse = await componentsAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,
        editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start component edit.');
        setIsGeneratingComponents(false);
        return;
      }

      // Only close modal once the edit job has started successfully
      setCurrentComponentJob(null);
      setViewingComponentJob(null);

      showSuccess('Editing components...');

      const finalJob = await componentsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentComponentJob(job)
      );

      setCurrentComponentJob(finalJob);

      if (finalJob.status === 'ready') {
        const count = finalJob.components?.length || 0;
        showSuccess(`Generated ${count} refined component${count !== 1 ? 's' : ''}!`);
        setSavedComponentJobs((prev) => [finalJob, ...prev]);
        setViewingComponentJob(finalJob);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Component edit failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'component edit failed');
      showError(error instanceof Error ? error.message : 'Component edit failed.');
    } finally {
      setIsGeneratingComponents(false);
      setCurrentComponentJob(null);
    }
  };

  return {
    savedComponentJobs,
    currentComponentJob,
    isGeneratingComponents,
    viewingComponentJob,
    setViewingComponentJob,
    loadSavedJobs,
    handleComponentGeneration,
    handleComponentEdit,
  };
};
