/**
 * useWireframeGeneration Hook
 * Educational Note: Manages Excalidraw wireframe generation from sources.
 * Creates UI/UX wireframes for visual prototyping.
 */

import { useState } from 'react';
import { wireframesAPI, type WireframeJob } from '@/lib/api/studio/wireframes';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('wireframe-generation');

export const useWireframeGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedWireframeJobs, setSavedWireframeJobs] = useState<WireframeJob[]>([]);
  const [currentWireframeJob, setCurrentWireframeJob] = useState<WireframeJob | null>(null);
  const [isGeneratingWireframe, setIsGeneratingWireframe] = useState(false);
  const [viewingWireframeJob, setViewingWireframeJob] = useState<WireframeJob | null>(null);

  const loadSavedJobs = async () => {
    const response = await wireframesAPI.listJobs(projectId);
    if (response.success && response.jobs) {
      const completedWireframes = response.jobs.filter((job) => job.status === 'ready');
      setSavedWireframeJobs(completedWireframes);
    }
  };

  const handleWireframeGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for wireframe generation.');
      return;
    }

    setIsGeneratingWireframe(true);
    setCurrentWireframeJob(null);

    try {
      const startResponse = await wireframesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start wireframe generation.');
        setIsGeneratingWireframe(false);
        return;
      }

      showSuccess(`Generating wireframe for ${startResponse.source_name}...`);

      const finalJob = await wireframesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentWireframeJob(job)
      );

      setCurrentWireframeJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated wireframe: ${finalJob.title} (${finalJob.element_count} elements)`);
        setSavedWireframeJobs((prev) => [finalJob, ...prev]);
        setViewingWireframeJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Wireframe generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LWireframe generationE failed');
      showError(error instanceof Error ? error.message : 'Wireframe generation failed.');
    } finally {
      setIsGeneratingWireframe(false);
      setCurrentWireframeJob(null);
    }
  };

  return {
    savedWireframeJobs,
    currentWireframeJob,
    isGeneratingWireframe,
    viewingWireframeJob,
    setViewingWireframeJob,
    loadSavedJobs,
    handleWireframeGeneration,
  };
};
