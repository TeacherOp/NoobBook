/**
 * Flash Cards API
 * Educational Note: Handles AI-generated flash cards for learning content.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-flash-cards-api');

/**
 * Flash card item
 */
export interface FlashCard {
  front: string;
  back: string;
  category: 'definition' | 'concept' | 'application' | 'comparison';
}

/**
 * Flash card job record from the API
 */
export interface FlashCardJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  cards: FlashCard[];
  topic_summary: string | null;
  card_count: number;
  generation_time_seconds: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting flash card generation
 */
export interface StartFlashCardsResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting flash card job status
 */
export interface FlashCardJobStatusResponse {
  success: boolean;
  job?: FlashCardJob;
  error?: string;
}

/**
 * Response from listing flash card jobs
 */
export interface ListFlashCardJobsResponse {
  success: boolean;
  jobs: FlashCardJob[];
  count: number;
  error?: string;
}

/**
 * Flash Cards API
 */
export const flashCardsAPI = {
  /**
   * Start flash card generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartFlashCardsResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/flash-cards`,
        {
          source_id: sourceId,
          direction: direction || 'Create flash cards covering the key concepts.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start flash card generation');
      throw error;
    }
  },

  /**
   * Get the status of a flash card job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<FlashCardJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/flash-card-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get flash card job status');
      throw error;
    }
  },

  /**
   * List all flash card jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListFlashCardJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/flash-card-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list flash card jobs');
      throw error;
    }
  },

  /**
   * Poll flash card job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: FlashCardJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 60
  ): Promise<FlashCardJob> {
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

    throw new Error('Flash card generation timed out');
  },
};
