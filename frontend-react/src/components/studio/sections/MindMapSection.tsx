/**
 * MindMapSection Component
 * Educational Note: Self-contained section for mind map generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useMindMapGeneration } from '../mindmap/useMindMapGeneration';
import { MindMapListItem } from '../mindmap/MindMapListItem';
import { MindMapProgressIndicator } from '../mindmap/MindMapProgressIndicator';
import { MindMapViewerModal } from '../mindmap/MindMapViewerModal';

export const MindMapSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedMindMapJobs,
    currentMindMapJob,
    isGeneratingMindMap,
    viewingMindMapJob,
    setViewingMindMapJob,
    loadSavedJobs,
    handleMindMapGeneration,
  } = useMindMapGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedMindMapJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleMindMapGeneration>[0]) => {
    await handleMindMapGeneration(signal);
  }, [handleMindMapGeneration]);

  useEffect(() => {
    registerGenerationHandler('mind_map', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingMindMap) {
    return null;
  }

  return (
    <>
      {isGeneratingMindMap && (
        <MindMapProgressIndicator currentMindMapJob={currentMindMapJob} />
      )}

      {filteredJobs.map((job) => (
        <MindMapListItem
          key={job.id}
          job={job}
          onClick={() => setViewingMindMapJob(job)}
        />
      ))}

      <MindMapViewerModal
        viewingMindMapJob={viewingMindMapJob}
        onClose={() => setViewingMindMapJob(null)}
      />
    </>
  );
};
