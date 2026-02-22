/**
 * useFlowDiagramGeneration Hook
 * Educational Note: Manages Mermaid flow diagram generation from sources.
 * Creates various diagram types (flowchart, sequence, state, ER, etc.) for visualization.
 */

import { useState } from 'react';
import { flowDiagramsAPI, type FlowDiagramJob } from '@/lib/api/studio';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('flow-diagram-generation');

export const useFlowDiagramGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedFlowDiagramJobs, setSavedFlowDiagramJobs] = useState<FlowDiagramJob[]>([]);
  const [currentFlowDiagramJob, setCurrentFlowDiagramJob] = useState<FlowDiagramJob | null>(null);
  const [isGeneratingFlowDiagram, setIsGeneratingFlowDiagram] = useState(false);
  const [viewingFlowDiagramJob, setViewingFlowDiagramJob] = useState<FlowDiagramJob | null>(null);

  const loadSavedJobs = async () => {
    const response = await flowDiagramsAPI.listJobs(projectId);
    if (response.success && response.jobs) {
      const completedDiagrams = response.jobs.filter((job) => job.status === 'ready');
      setSavedFlowDiagramJobs(completedDiagrams);
    }
  };

  const handleFlowDiagramGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for flow diagram generation.');
      return;
    }

    setIsGeneratingFlowDiagram(true);
    setCurrentFlowDiagramJob(null);

    try {
      const startResponse = await flowDiagramsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start flow diagram generation.');
        setIsGeneratingFlowDiagram(false);
        return;
      }

      showSuccess(`Generating flow diagram for ${startResponse.source_name}...`);

      const finalJob = await flowDiagramsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentFlowDiagramJob(job)
      );

      setCurrentFlowDiagramJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.diagram_type} diagram: ${finalJob.title}`);
        setSavedFlowDiagramJobs((prev) => [finalJob, ...prev]);
        setViewingFlowDiagramJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Flow diagram generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LFlow diagram generationE failed');
      showError(error instanceof Error ? error.message : 'Flow diagram generation failed.');
    } finally {
      setIsGeneratingFlowDiagram(false);
      setCurrentFlowDiagramJob(null);
    }
  };

  return {
    savedFlowDiagramJobs,
    currentFlowDiagramJob,
    isGeneratingFlowDiagram,
    viewingFlowDiagramJob,
    setViewingFlowDiagramJob,
    loadSavedJobs,
    handleFlowDiagramGeneration,
  };
};
