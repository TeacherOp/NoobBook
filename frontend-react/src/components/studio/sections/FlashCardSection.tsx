/**
 * FlashCardSection Component
 * Educational Note: Self-contained section for flash card generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useFlashCardGeneration } from '../flashcards/useFlashCardGeneration';
import { FlashCardListItem } from '../flashcards/FlashCardListItem';
import { FlashCardProgressIndicator } from '../flashcards/FlashCardProgressIndicator';
import { FlashCardViewerModal } from '../flashcards/FlashCardViewerModal';

export const FlashCardSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedFlashCardJobs,
    currentFlashCardJob,
    isGeneratingFlashCards,
    viewingFlashCardJob,
    setViewingFlashCardJob,
    loadSavedJobs,
    handleFlashCardGeneration,
  } = useFlashCardGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedFlashCardJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleFlashCardGeneration>[0]) => {
    await handleFlashCardGeneration(signal);
  }, [handleFlashCardGeneration]);

  useEffect(() => {
    registerGenerationHandler('flash_cards', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingFlashCards) {
    return null;
  }

  return (
    <>
      {isGeneratingFlashCards && (
        <FlashCardProgressIndicator currentFlashCardJob={currentFlashCardJob} />
      )}

      {filteredJobs.map((job) => (
        <FlashCardListItem
          key={job.id}
          job={job}
          onClick={() => setViewingFlashCardJob(job)}
        />
      ))}

      <FlashCardViewerModal
        viewingFlashCardJob={viewingFlashCardJob}
        onClose={() => setViewingFlashCardJob(null)}
      />
    </>
  );
};
