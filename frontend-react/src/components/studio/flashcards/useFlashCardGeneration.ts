/**
 * useFlashCardGeneration Hook
 * Educational Note: Custom hook for flash card generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState } from 'react';
import { flashCardsAPI, type FlashCardJob } from '@/lib/api/studio';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('flash-card-generation');

export const useFlashCardGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedFlashCardJobs, setSavedFlashCardJobs] = useState<FlashCardJob[]>([]);
  const [currentFlashCardJob, setCurrentFlashCardJob] = useState<FlashCardJob | null>(null);
  const [isGeneratingFlashCards, setIsGeneratingFlashCards] = useState(false);
  const [viewingFlashCardJob, setViewingFlashCardJob] = useState<FlashCardJob | null>(null);

  /**
   * Load saved flash card jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const flashCardResponse = await flashCardsAPI.listJobs(projectId);
      if (flashCardResponse.success && flashCardResponse.jobs) {
        const completedFlashCards = flashCardResponse.jobs.filter((job) => job.status === 'ready');
        setSavedFlashCardJobs(completedFlashCards);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved flash card jobs');
    }
  };

  /**
   * Handle flash card generation
   */
  const handleFlashCardGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for flash card generation.');
      return;
    }

    setIsGeneratingFlashCards(true);
    setCurrentFlashCardJob(null);

    try {
      const startResponse = await flashCardsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start flash card generation.');
        setIsGeneratingFlashCards(false);
        return;
      }

      showSuccess(`Generating flash cards for ${startResponse.source_name}...`);

      const finalJob = await flashCardsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentFlashCardJob(job)
      );

      setCurrentFlashCardJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.card_count} flash cards!`);
        setSavedFlashCardJobs((prev) => [finalJob, ...prev]);
        setViewingFlashCardJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Flash card generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LFlash card generationE failed');
      showError(error instanceof Error ? error.message : 'Flash card generation failed.');
    } finally {
      setIsGeneratingFlashCards(false);
      setCurrentFlashCardJob(null);
    }
  };

  return {
    savedFlashCardJobs,
    currentFlashCardJob,
    isGeneratingFlashCards,
    viewingFlashCardJob,
    setViewingFlashCardJob,
    loadSavedJobs,
    handleFlashCardGeneration,
  };
};
