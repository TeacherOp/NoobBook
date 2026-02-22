/**
 * Infographics API
 * Educational Note: Handles AI-generated infographic images using Gemini Imagen.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-infographics-api');

/**
 * Infographic image info
 */
export interface InfographicImage {
  filename: string;
  path: string;
  index: number;
}

/**
 * Infographic key section (for display)
 */
export interface InfographicKeySection {
  title: string;
  icon_description: string;
}

/**
 * Infographic job record from the API
 */
export interface InfographicJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  topic_title: string | null;
  topic_summary: string | null;
  key_sections: InfographicKeySection[];
  image: InfographicImage | null;
  image_url: string | null;
  image_prompt: string | null;
  generation_time_seconds: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting infographic generation
 */
export interface StartInfographicResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting infographic job status
 */
export interface InfographicJobStatusResponse {
  success: boolean;
  job?: InfographicJob;
  error?: string;
}

/**
 * Response from listing infographic jobs
 */
export interface ListInfographicJobsResponse {
  success: boolean;
  jobs: InfographicJob[];
  count: number;
  error?: string;
}

/**
 * Infographics API
 */
export const infographicsAPI = {
  /**
   * Start infographic generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartInfographicResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/infographic`,
        {
          source_id: sourceId,
          direction: direction || 'Create an informative infographic summarizing the key concepts.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start infographic generation');
      throw error;
    }
  },

  /**
   * Get the status of an infographic job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<InfographicJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/infographic-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get infographic job status');
      throw error;
    }
  },

  /**
   * List all infographic jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListInfographicJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/infographic-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list infographic jobs');
      throw error;
    }
  },

  /**
   * Get the full URL for an infographic image
   */
  getImageUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/infographics/${jobId}/${filename}`;
  },

  /**
   * Poll infographic job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: InfographicJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120
  ): Promise<InfographicJob> {
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

    throw new Error('Infographic generation timed out');
  },
};
