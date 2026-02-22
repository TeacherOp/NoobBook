/**
 * Marketing Strategies API
 * Educational Note: Handles AI-generated Marketing Strategy Documents.
 * Marketing strategies are written incrementally by the agent and stored as markdown files.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-marketing-strategies-api');

/**
 * Marketing Strategy job record from the API
 */
export interface MarketingStrategyJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  status_message: string;
  error_message: string | null;

  // Plan fields
  document_title: string | null;
  product_name: string | null;
  target_market: string | null;
  planned_sections: Array<{
    section_id: string;
    title: string;
    description: string;
    priority?: string;
  }>;
  planning_notes: string | null;

  // Progress tracking
  sections_written: number;
  total_sections: number;
  current_section: string | null;

  // Generated content
  markdown_file: string | null;
  markdown_filename: string | null;

  // URLs
  preview_url: string | null;
  download_url: string | null;

  // Metadata
  iterations: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting marketing strategy generation
 */
export interface StartMarketingStrategyResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting marketing strategy job status
 */
export interface MarketingStrategyJobStatusResponse {
  success: boolean;
  job?: MarketingStrategyJob;
  error?: string;
}

/**
 * Response from listing marketing strategy jobs
 */
export interface ListMarketingStrategyJobsResponse {
  success: boolean;
  jobs: MarketingStrategyJob[];
  error?: string;
}

/**
 * Response from preview endpoint
 */
export interface MarketingStrategyPreviewResponse {
  success: boolean;
  document_title?: string;
  product_name?: string;
  sections_written?: number;
  total_sections?: number;
  markdown_content?: string;
  status?: JobStatus;
  error?: string;
}

/**
 * Marketing Strategies API
 */
export const marketingStrategiesAPI = {
  /**
   * Start marketing strategy generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartMarketingStrategyResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/marketing-strategy`,
        {
          source_id: sourceId,
          direction: direction || 'Create a comprehensive marketing strategy covering all relevant aspects.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start marketing strategy generation');
      throw error;
    }
  },

  /**
   * Get the status of a marketing strategy job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<MarketingStrategyJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/marketing-strategy-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get marketing strategy job status');
      throw error;
    }
  },

  /**
   * List all marketing strategy jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListMarketingStrategyJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/marketing-strategy-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list marketing strategy jobs');
      throw error;
    }
  },

  /**
   * Get marketing strategy preview (markdown content)
   */
  async getPreview(projectId: string, jobId: string): Promise<MarketingStrategyPreviewResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/marketing-strategies/${jobId}/preview`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get marketing strategy preview');
      throw error;
    }
  },

  /**
   * Get download URL for marketing strategy
   */
  getDownloadUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/marketing-strategies/${jobId}/download`;
  },

  /**
   * Poll marketing strategy job status until complete or error
   * Educational Note: Added initial delay to avoid race condition where
   * the job might not be saved to disk yet when polling starts.
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: MarketingStrategyJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120 // Marketing strategies can take longer
  ): Promise<MarketingStrategyJob> {
    let attempts = 0;
    let currentInterval = intervalMs;

    // Initial delay to let the job be created and saved
    await new Promise((resolve) => setTimeout(resolve, 1000));

    while (attempts < maxAttempts) {
      const response = await this.getJobStatus(projectId, jobId);

      // Handle race condition: job might not exist yet in first few attempts
      if (!response.success || !response.job) {
        if (attempts < 3) {
          // Give the backend more time to create the job
          await new Promise((resolve) => setTimeout(resolve, currentInterval));
          attempts++;
          continue;
        }
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

      // Gradually increase interval for long-running jobs
      if (attempts > 5 && currentInterval < 5000) {
        currentInterval = Math.min(currentInterval * 1.2, 5000);
      }
    }

    throw new Error('Marketing strategy generation timed out');
  },
};
