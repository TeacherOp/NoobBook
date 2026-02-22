/**
 * Ad Creatives API
 * Educational Note: Handles AI-generated ad creative images using Gemini Imagen.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-ads-api');

/**
 * Ad creative image info
 */
export interface AdImage {
  filename: string;
  path: string;
  url: string;
  type: string;
  prompt: string;
  index: number;
}

/**
 * Ad creative job record from the API
 */
export interface AdJob {
  id: string;
  product_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  images: AdImage[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting ad creative generation
 */
export interface StartAdResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  product_name?: string;
  error?: string;
}

/**
 * Response from getting ad job status
 */
export interface AdJobStatusResponse {
  success: boolean;
  job?: AdJob;
  error?: string;
}

/**
 * Response from listing ad jobs
 */
export interface ListAdJobsResponse {
  success: boolean;
  jobs: AdJob[];
  count: number;
  error?: string;
}

/**
 * Ad Creatives API
 */
export const adsAPI = {
  /**
   * Start ad creative generation
   */
  async startGeneration(
    projectId: string,
    productName: string,
    direction?: string
  ): Promise<StartAdResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/ad-creative`,
        {
          product_name: productName,
          direction: direction || 'Create compelling ad creatives for Facebook and Instagram.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start ad generation');
      throw error;
    }
  },

  /**
   * Get the status of an ad creative job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<AdJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/ad-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get ad job status');
      throw error;
    }
  },

  /**
   * List all ad jobs for a project
   */
  async listJobs(projectId: string): Promise<ListAdJobsResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/ad-jobs`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list ad jobs');
      throw error;
    }
  },

  /**
   * Get the full URL for an ad creative image
   */
  getCreativeUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/creatives/${jobId}/${filename}`;
  },

  /**
   * Poll ad job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: AdJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120
  ): Promise<AdJob> {
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

    throw new Error('Ad creative generation timed out');
  },
};
