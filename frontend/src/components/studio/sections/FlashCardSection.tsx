/**
 * FlashCardSection Component
 * Educational Note: Self-contained section for flash card generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
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
    pendingEditInput,
    loadSavedJobs,
    handleFlashCardGeneration,
    handleFlashCardEdit,
    handleFlashCardDelete,
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
        <FlashCardProgressIndicator currentFlashCardJob={currentFlashCardJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <FlashCardListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onClick={() => setViewingFlashCardJob(job)}
          onDelete={() => handleFlashCardDelete(job.id)}
        />
      ))}

      <FlashCardViewerModal
        viewingFlashCardJob={viewingFlashCardJob}
        onClose={() => setViewingFlashCardJob(null)}
        onEdit={(instructions) => viewingFlashCardJob && handleFlashCardEdit(viewingFlashCardJob, instructions)}
        isGenerating={isGeneratingFlashCards}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
