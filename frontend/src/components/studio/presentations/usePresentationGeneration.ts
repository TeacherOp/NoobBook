/**
 * usePresentationGeneration Hook
 * Educational Note: Custom hook for presentation generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState } from 'react';
import { presentationsAPI, type PresentationJob } from '@/lib/api/studio';
import { useToast } from '../../ui/toast';
import type { StudioSignal } from '../types';

export const usePresentationGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedPresentationJobs, setSavedPresentationJobs] = useState<PresentationJob[]>([]);
  const [currentPresentationJob, setCurrentPresentationJob] = useState<PresentationJob | null>(null);
  const [isGeneratingPresentation, setIsGeneratingPresentation] = useState(false);
  const [viewingPresentationJob, setViewingPresentationJob] = useState<PresentationJob | null>(null);

  /**
   * Load saved presentation jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const response = await presentationsAPI.listJobs(projectId);
      if (response.success && response.jobs) {
        // Only show jobs that are ready and have PPTX exported
        const completedPresentations = response.jobs.filter(
          (job) => job.status === 'ready' && job.export_status === 'ready'
        );
        setSavedPresentationJobs(completedPresentations);
      }
    } catch (error) {
      console.error('Failed to load saved presentation jobs:', error);
    }
  };

  /**
   * Handle presentation generation
   * Educational Note: Presentations auto-open in viewer after generation
   */
  const handlePresentationGeneration = async (signal: StudioSignal) => {
    setIsGeneratingPresentation(true);
    setCurrentPresentationJob(null);

    try {
      const sourceId = signal.sources[0]?.source_id;
      if (!sourceId) {
        showError('No source selected');
        return;
      }

      // Start presentation generation
      const startResponse = await presentationsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start presentation generation');
        return;
      }

      // Poll for completion (including PPTX export)
      const finalJob = await presentationsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentPresentationJob(job)
      );

      if (finalJob.status === 'ready' && finalJob.export_status === 'ready') {
        setSavedPresentationJobs((prev) => [finalJob, ...prev]);
        // Open presentation in viewer automatically
        setViewingPresentationJob(finalJob);
        showSuccess('Presentation generated successfully!');
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Presentation generation failed');
      }
    } catch (error) {
      console.error('Presentation generation error:', error);
      showError('Presentation generation failed');
    } finally {
      setIsGeneratingPresentation(false);
      setCurrentPresentationJob(null);
    }
  };

  /**
   * Download presentation as PPTX
   */
  const downloadPresentation = (jobId: string) => {
    // API_BASE_URL already includes /api/v1 path
    const downloadUrl = presentationsAPI.getDownloadUrl(projectId, jobId, 'pptx');
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.click();
  };

  /**
   * Download presentation source as ZIP
   */
  const downloadPresentationSource = (jobId: string) => {
    // API_BASE_URL already includes /api/v1 path
    const downloadUrl = presentationsAPI.getDownloadUrl(projectId, jobId, 'zip');
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.click();
  };

  return {
    savedPresentationJobs,
    currentPresentationJob,
    isGeneratingPresentation,
    viewingPresentationJob,
    setViewingPresentationJob,
    loadSavedJobs,
    handlePresentationGeneration,
    downloadPresentation,
    downloadPresentationSource,
  };
};
