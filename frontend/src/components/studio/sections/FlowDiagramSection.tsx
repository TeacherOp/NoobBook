/**
 * FlowDiagramSection Component
 * Educational Note: Self-contained section for flow diagram generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { useFlowDiagramGeneration } from '../flow-diagrams/useFlowDiagramGeneration';
import { FlowDiagramListItem } from '../flow-diagrams/FlowDiagramListItem';
import { FlowDiagramProgressIndicator } from '../flow-diagrams/FlowDiagramProgressIndicator';
import { FlowDiagramViewerModal } from '../flow-diagrams/FlowDiagramViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const FlowDiagramSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedFlowDiagramJobs,
    currentFlowDiagramJob,
    isGeneratingFlowDiagram,
    viewingFlowDiagramJob,
    setViewingFlowDiagramJob,
    configError,
    pendingEditInput,
    loadSavedJobs,
    handleFlowDiagramGeneration,
    handleFlowDiagramEdit,
    handleFlowDiagramDelete,
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

  if (filteredJobs.length === 0 && !isGeneratingFlowDiagram && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingFlowDiagram && (
        <FlowDiagramProgressIndicator currentFlowDiagramJob={currentFlowDiagramJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <FlowDiagramListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onClick={() => setViewingFlowDiagramJob(job)}
          onDelete={() => handleFlowDiagramDelete(job.id)}
        />
      ))}

      <FlowDiagramViewerModal
        job={viewingFlowDiagramJob}
        onClose={() => setViewingFlowDiagramJob(null)}
        onEdit={(instructions) => viewingFlowDiagramJob && handleFlowDiagramEdit(viewingFlowDiagramJob, instructions)}
        isGenerating={isGeneratingFlowDiagram}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
