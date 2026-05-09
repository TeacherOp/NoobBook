/**
 * QuizSection Component
 * Educational Note: Self-contained section for quiz generation.
 * Owns all quiz-related state - isolated from other sections.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { useQuizGeneration } from '../quiz/useQuizGeneration';
import { QuizListItem } from '../quiz/QuizListItem';
import { QuizProgressIndicator } from '../quiz/QuizProgressIndicator';
import { QuizViewerModal } from '../quiz/QuizViewerModal';

export const QuizSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedQuizJobs,
    currentQuizJob,
    isGeneratingQuiz,
    viewingQuizJob,
    setViewingQuizJob,
    pendingEditInput,
    loadSavedJobs,
    handleQuizGeneration,
    handleQuizEdit,
    handleQuizDelete,
  } = useQuizGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedQuizJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleQuizGeneration>[0]) => {
    await handleQuizGeneration(signal);
  }, [handleQuizGeneration]);

  useEffect(() => {
    registerGenerationHandler('quiz', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingQuiz) {
    return null;
  }

  return (
    <>
      {isGeneratingQuiz && (
        <QuizProgressIndicator currentQuizJob={currentQuizJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <QuizListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onClick={() => setViewingQuizJob(job)}
          onDelete={() => handleQuizDelete(job.id)}
        />
      ))}

      <QuizViewerModal
        viewingQuizJob={viewingQuizJob}
        onClose={() => setViewingQuizJob(null)}
        onEdit={(instructions) => viewingQuizJob && handleQuizEdit(viewingQuizJob, instructions)}
        isGenerating={isGeneratingQuiz}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
