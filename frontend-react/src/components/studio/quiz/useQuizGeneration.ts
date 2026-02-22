/**
 * useQuizGeneration Hook
 * Educational Note: Manages quiz generation from sources.
 * Creates interactive quiz questions with multiple choice answers.
 */

import { useState } from 'react';
import { quizzesAPI, type QuizJob } from '@/lib/api/studio';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('quiz-generation');

export const useQuizGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedQuizJobs, setSavedQuizJobs] = useState<QuizJob[]>([]);
  const [currentQuizJob, setCurrentQuizJob] = useState<QuizJob | null>(null);
  const [isGeneratingQuiz, setIsGeneratingQuiz] = useState(false);
  const [viewingQuizJob, setViewingQuizJob] = useState<QuizJob | null>(null);

  const loadSavedJobs = async () => {
    const quizResponse = await quizzesAPI.listJobs(projectId);
    if (quizResponse.success && quizResponse.jobs) {
      const completedQuizzes = quizResponse.jobs.filter((job) => job.status === 'ready');
      setSavedQuizJobs(completedQuizzes);
    }
  };

  const handleQuizGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for quiz generation.');
      return;
    }

    setIsGeneratingQuiz(true);
    setCurrentQuizJob(null);

    try {
      const startResponse = await quizzesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start quiz generation.');
        setIsGeneratingQuiz(false);
        return;
      }

      showSuccess(`Generating quiz for ${startResponse.source_name}...`);

      const finalJob = await quizzesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentQuizJob(job)
      );

      setCurrentQuizJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.question_count} quiz questions!`);
        setSavedQuizJobs((prev) => [finalJob, ...prev]);
        setViewingQuizJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Quiz generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LQuiz generationE failed');
      showError(error instanceof Error ? error.message : 'Quiz generation failed.');
    } finally {
      setIsGeneratingQuiz(false);
      setCurrentQuizJob(null);
    }
  };

  return {
    savedQuizJobs,
    currentQuizJob,
    isGeneratingQuiz,
    viewingQuizJob,
    setViewingQuizJob,
    loadSavedJobs,
    handleQuizGeneration,
  };
};
