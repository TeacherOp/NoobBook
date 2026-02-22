/**
 * Mind Maps API
 * Educational Note: Handles AI-generated mind maps for visualizing content structure.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-mind-maps-api');

/**
 * Mind map node from Claude
 */
export interface MindMapNode {
  id: string;
  label: string;
  parent_id: string | null;
  node_type: 'root' | 'category' | 'leaf';
  description: string;
}

/**
 * Mind map job record from the API
 */
export interface MindMapJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  nodes: MindMapNode[];
  topic_summary: string | null;
  node_count: number;
  generation_time_seconds: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting mind map generation
 */
export interface StartMindMapResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting mind map job status
 */
export interface MindMapJobStatusResponse {
  success: boolean;
  job?: MindMapJob;
  error?: string;
}

/**
 * Response from listing mind map jobs
 */
export interface ListMindMapJobsResponse {
  success: boolean;
  jobs: MindMapJob[];
  count: number;
  error?: string;
}

/**
 * Mind Maps API
 */
export const mindMapsAPI = {
  /**
   * Start mind map generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartMindMapResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/mind-map`,
        {
          source_id: sourceId,
          direction: direction || 'Create a mind map covering the key concepts and their relationships.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start mind map generation');
      throw error;
    }
  },

  /**
   * Get the status of a mind map job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<MindMapJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/mind-map-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get mind map job status');
      throw error;
    }
  },

  /**
   * List all mind map jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListMindMapJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/mind-map-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list mind map jobs');
      throw error;
    }
  },

  /**
   * Poll mind map job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: MindMapJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 60
  ): Promise<MindMapJob> {
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

    throw new Error('Mind map generation timed out');
  },
};
