/**
 * Quizzes API
 * Educational Note: Handles AI-generated quizzes for testing knowledge.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-quizzes-api');

/**
 * Quiz option (answer choice)
 */
export interface QuizOption {
  id: string;
  text: string;
}

/**
 * Quiz question from Claude
 */
export interface QuizQuestion {
  id: string;
  question: string;
  options: QuizOption[];
  correct_answers: string[];
  is_multi_select: boolean;
  hint?: string;
  explanation: string;
}

/**
 * Quiz job record from the API
 */
export interface QuizJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  questions: QuizQuestion[];
  topic_summary: string | null;
  question_count: number;
  generation_time_seconds: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting quiz generation
 */
export interface StartQuizResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting quiz job status
 */
export interface QuizJobStatusResponse {
  success: boolean;
  job?: QuizJob;
  error?: string;
}

/**
 * Response from listing quiz jobs
 */
export interface ListQuizJobsResponse {
  success: boolean;
  jobs: QuizJob[];
  count: number;
  error?: string;
}

/**
 * Quizzes API
 */
export const quizzesAPI = {
  /**
   * Start quiz generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartQuizResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/quiz`,
        {
          source_id: sourceId,
          direction: direction || 'Create quiz questions covering the key concepts.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start quiz generation');
      throw error;
    }
  },

  /**
   * Get the status of a quiz job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<QuizJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/quiz-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get quiz job status');
      throw error;
    }
  },

  /**
   * List all quiz jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListQuizJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/quiz-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list quiz jobs');
      throw error;
    }
  },

  /**
   * Poll quiz job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: QuizJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 60
  ): Promise<QuizJob> {
    let attempts = 0;
    let currentInterval = intervalMs;

    while (attempts < maxAttempts) {
      const response = await this.getJobStatus(projectId, jobId);

      if (!response.success || !response.job) {
        throw new Error(response.error || 'Failed to get job status');
      }

      const job = response.job;

      if (onProgress) {
        onProgress(job);
      }

      if (job.status === 'ready' || job.status === 'error') {
        return job;
      }

      await new Promise((resolve) => setTimeout(resolve, currentInterval));

      attempts++;

      if (attempts > 5 && currentInterval < 5000) {
        currentInterval = Math.min(currentInterval * 1.2, 5000);
      }
    }

    throw new Error('Quiz generation timed out');
  },
};
