/**
 * Components API
 * Educational Note: Handles AI-generated UI components (HTML/CSS/JS).
 * Uses an agentic approach for multi-variation generation.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-components-api');

/**
 * Component variation info
 */
export interface ComponentVariation {
  variation_name: string;
  filename: string;
  description: string;
  preview_url: string;
  char_count: number;
}

/**
 * Planned component variation
 */
export interface PlannedVariation {
  variation_name: string;
  style_approach: string;
  key_features: string[];
}

/**
 * Component generation job
 */
export interface ComponentJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  status_message: string;
  error_message: string | null;
  // Component plan
  component_category: 'button' | 'card' | 'form' | 'navigation' | 'modal' | 'list' | 'grid' | 'hero' | 'pricing' | 'testimonial' | 'footer' | 'other' | null;
  component_description: string | null;
  variations_planned: PlannedVariation[];
  technical_notes: string | null;
  // Generated content
  components: ComponentVariation[];
  usage_notes: string | null;
  // Metadata
  iterations: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting component generation
 */
export interface StartComponentResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting component job status
 */
export interface ComponentJobStatusResponse {
  success: boolean;
  job?: ComponentJob;
  error?: string;
}

/**
 * Response from listing component jobs
 */
export interface ListComponentJobsResponse {
  success: boolean;
  jobs: ComponentJob[];
  error?: string;
}

/**
 * Components API
 */
export const componentsAPI = {
  /**
   * Start component generation via component agent
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartComponentResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/components`,
        {
          source_id: sourceId,
          direction: direction || '',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start component generation');
      throw error;
    }
  },

  /**
   * Get the status of a component generation job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<ComponentJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/component-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get component job status');
      throw error;
    }
  },

  /**
   * List all component generation jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListComponentJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/component-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list component jobs');
      throw error;
    }
  },

  /**
   * Get the preview URL for a component
   */
  getPreviewUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/components/${jobId}/preview/${filename}`;
  },

  /**
   * Poll component job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: ComponentJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120
  ): Promise<ComponentJob> {
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

    throw new Error('Component generation timed out');
  },
};
