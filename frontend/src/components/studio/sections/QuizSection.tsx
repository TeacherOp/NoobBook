/**
 * QuizSection Component
 * Educational Note: Self-contained section for quiz generation.
 * Owns all quiz-related state - isolated from other sections.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
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
    loadSavedJobs,
    handleQuizGeneration,
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
        <QuizProgressIndicator currentQuizJob={currentQuizJob} />
      )}

      {filteredJobs.map((job) => (
        <QuizListItem
          key={job.id}
          job={job}
          onClick={() => setViewingQuizJob(job)}
        />
      ))}

      <QuizViewerModal
        viewingQuizJob={viewingQuizJob}
        onClose={() => setViewingQuizJob(null)}
      />
    </>
  );
};
