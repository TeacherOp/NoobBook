/**
 * PRDs API
 * Educational Note: Handles AI-generated Product Requirements Documents.
 * PRDs are written incrementally by the agent and stored as markdown files.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-prds-api');

/**
 * PRD job record from the API
 */
export interface PRDJob {
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
  target_audience: string | null;
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
 * Response from starting PRD generation
 */
export interface StartPRDResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting PRD job status
 */
export interface PRDJobStatusResponse {
  success: boolean;
  job?: PRDJob;
  error?: string;
}

/**
 * Response from listing PRD jobs
 */
export interface ListPRDJobsResponse {
  success: boolean;
  jobs: PRDJob[];
  error?: string;
}

/**
 * Response from preview endpoint
 */
export interface PRDPreviewResponse {
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
 * PRDs API
 */
export const prdsAPI = {
  /**
   * Start PRD generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartPRDResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/prd`,
        {
          source_id: sourceId,
          direction: direction || 'Create a comprehensive PRD covering all relevant product requirements.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start PRD generation');
      throw error;
    }
  },

  /**
   * Get the status of a PRD job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<PRDJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/prd-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get PRD job status');
      throw error;
    }
  },

  /**
   * List all PRD jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListPRDJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/prd-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list PRD jobs');
      throw error;
    }
  },

  /**
   * Get PRD preview (markdown content)
   */
  async getPreview(projectId: string, jobId: string): Promise<PRDPreviewResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/prds/${jobId}/preview`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get PRD preview');
      throw error;
    }
  },

  /**
   * Get download URL for PRD
   */
  getDownloadUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/prds/${jobId}/download`;
  },

  /**
   * Poll PRD job status until complete or error
   * Educational Note: Added initial delay to avoid race condition where
   * the job might not be saved to disk yet when polling starts.
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: PRDJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120 // PRDs can take longer
  ): Promise<PRDJob> {
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

    throw new Error('PRD generation timed out');
  },
};
