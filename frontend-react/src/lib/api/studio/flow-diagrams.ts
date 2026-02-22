/**
 * Flow Diagrams API
 * Educational Note: Handles AI-generated Mermaid diagrams for visualizing
 * processes, workflows, relationships, and more.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-flow-diagrams-api');

/**
 * Mermaid diagram types supported
 */
export type DiagramType =
  | 'flowchart'
  | 'sequence'
  | 'state'
  | 'er'
  | 'class'
  | 'pie'
  | 'gantt'
  | 'journey'
  | 'mindmap';

/**
 * Flow diagram job record from the API
 */
export interface FlowDiagramJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  progress: string;
  error: string | null;
  mermaid_syntax: string | null;
  diagram_type: DiagramType | null;
  title: string | null;
  description: string | null;
  generation_time_seconds: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting flow diagram generation
 */
export interface StartFlowDiagramResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting flow diagram job status
 */
export interface FlowDiagramJobStatusResponse {
  success: boolean;
  job?: FlowDiagramJob;
  error?: string;
}

/**
 * Response from listing flow diagram jobs
 */
export interface ListFlowDiagramJobsResponse {
  success: boolean;
  jobs: FlowDiagramJob[];
  count: number;
  error?: string;
}

/**
 * Flow Diagrams API
 */
export const flowDiagramsAPI = {
  /**
   * Start flow diagram generation
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartFlowDiagramResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/flow-diagram`,
        {
          source_id: sourceId,
          direction: direction || 'Create a diagram showing the key processes and relationships.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start flow diagram generation');
      throw error;
    }
  },

  /**
   * Get the status of a flow diagram job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<FlowDiagramJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/flow-diagram-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get flow diagram job status');
      throw error;
    }
  },

  /**
   * List all flow diagram jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListFlowDiagramJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/flow-diagram-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list flow diagram jobs');
      throw error;
    }
  },

  /**
   * Poll flow diagram job status until complete or error
   *
   * Educational Note: Includes initial retry tolerance to handle timing
   * between job creation and first poll availability.
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: FlowDiagramJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 60
  ): Promise<FlowDiagramJob> {
    let attempts = 0;
    let currentInterval = intervalMs;
    let initialRetries = 0;
    const maxInitialRetries = 3;

    while (attempts < maxAttempts) {
      const response = await this.getJobStatus(projectId, jobId);

      // Handle initial 404s with retry tolerance
      if (!response.success || !response.job) {
        if (initialRetries < maxInitialRetries) {
          log.debug(`flow diagram job not found yet, retrying... (${initialRetries + 1}/${maxInitialRetries})`);
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

    throw new Error('Flow diagram generation timed out');
  },
};
