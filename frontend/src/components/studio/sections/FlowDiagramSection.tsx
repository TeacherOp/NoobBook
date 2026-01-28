/**
 * FlowDiagramSection Component
 * Educational Note: Self-contained section for flow diagram generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useFlowDiagramGeneration } from '../flow-diagrams/useFlowDiagramGeneration';
import { FlowDiagramListItem } from '../flow-diagrams/FlowDiagramListItem';
import { FlowDiagramProgressIndicator } from '../flow-diagrams/FlowDiagramProgressIndicator';
import { FlowDiagramViewerModal } from '../flow-diagrams/FlowDiagramViewerModal';

export const FlowDiagramSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedFlowDiagramJobs,
    currentFlowDiagramJob,
    isGeneratingFlowDiagram,
    viewingFlowDiagramJob,
    setViewingFlowDiagramJob,
    loadSavedJobs,
    handleFlowDiagramGeneration,
  } = useFlowDiagramGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedFlowDiagramJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleFlowDiagramGeneration>[0]) => {
    await handleFlowDiagramGeneration(signal);
  }, [handleFlowDiagramGeneration]);

  useEffect(() => {
    registerGenerationHandler('flow_diagram', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingFlowDiagram) {
    return null;
  }

  return (
    <>
      {isGeneratingFlowDiagram && (
        <FlowDiagramProgressIndicator currentFlowDiagramJob={currentFlowDiagramJob} />
      )}

      {filteredJobs.map((job) => (
        <FlowDiagramListItem
          key={job.id}
          job={job}
          onClick={() => setViewingFlowDiagramJob(job)}
        />
      ))}

      <FlowDiagramViewerModal
        job={viewingFlowDiagramJob}
        onClose={() => setViewingFlowDiagramJob(null)}
      />
    </>
  );
};
