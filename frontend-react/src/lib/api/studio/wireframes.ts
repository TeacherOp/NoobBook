/**
 * Wireframes API
 * Educational Note: Handles AI-generated UI/UX wireframes using Excalidraw.
 * The backend generates Excalidraw element definitions which are rendered
 * using the Excalidraw React component.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-wireframes-api');

/**
 * Excalidraw element from the API
 */
export interface ExcalidrawElement {
  id: string;
  type: 'rectangle' | 'text' | 'line' | 'arrow' | 'ellipse' | 'diamond';
  x: number;
  y: number;
  width?: number;
  height?: number;
  text?: string;
  fontSize?: number;
  strokeColor: string;
  backgroundColor: string;
  fillStyle: 'solid' | 'hachure' | 'cross-hatch';
  strokeWidth: number;
  roughness: number;
  opacity: number;
  seed: number;
  points?: number[][];
  // Additional Excalidraw properties
  [key: string]: unknown;
}

/**
 * Wireframe job record from the API
 */
export interface WireframeJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  title: string | null;
  description: string | null;
  elements: ExcalidrawElement[];
  canvas_width: number;
  canvas_height: number;
  element_count: number;
  generation_time_seconds: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting wireframe generation
 */
export interface StartWireframeResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting wireframe job status
 */
export interface WireframeJobStatusResponse {
  success: boolean;
  job?: WireframeJob;
  error?: string;
}

/**
 * Response from listing wireframe jobs
 */
export interface ListWireframeJobsResponse {
  success: boolean;
  jobs: WireframeJob[];
  count: number;
  error?: string;
}

/**
 * Wireframes API
 */
export const wireframesAPI = {
  /**
   * Start wireframe generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartWireframeResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/wireframe`,
        {
          source_id: sourceId,
          direction: direction || 'Create a wireframe for the main page layout.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start wireframe generation');
      throw error;
    }
  },

  /**
   * Get the status of a wireframe job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<WireframeJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/wireframe-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get wireframe job status');
      throw error;
    }
  },

  /**
   * List all wireframe jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListWireframeJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/wireframe-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list wireframe jobs');
      throw error;
    }
  },

  /**
   * Poll wireframe job status until complete or error
   *
   * Educational Note: Includes initial retry tolerance to handle timing
   * between job creation and first poll availability.
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: WireframeJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 90 // Longer timeout for wireframes
  ): Promise<WireframeJob> {
    let attempts = 0;
    let currentInterval = intervalMs;
    let initialRetries = 0;
    const maxInitialRetries = 3;

    while (attempts < maxAttempts) {
      const response = await this.getJobStatus(projectId, jobId);

      // Handle initial 404s with retry tolerance
      if (!response.success || !response.job) {
        if (initialRetries < maxInitialRetries) {
          log.debug(`wireframe job not found yet, retrying (${initialRetries + 1}/${maxInitialRetries})`);
          initialRetries++;
          await new Promise((resolve) => setTimeout(resolve, 500));
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

      if (attempts > 5 && currentInterval < 5000) {
        currentInterval = Math.min(currentInterval * 1.2, 5000);
      }
    }

    throw new Error('Wireframe generation timed out');
  },
};
