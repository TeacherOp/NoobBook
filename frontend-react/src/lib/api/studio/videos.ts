/**
 * Videos API
 * Educational Note: Handles AI-generated videos using Google Veo.
 * Video generation can take 10-20 minutes.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-videos-api');

/**
 * Video file information
 */
export interface VideoFile {
  filename: string;
  path: string;
  uri: string;
  preview_url: string;
  download_url: string;
}

/**
 * Video generation job
 */
export interface VideoJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  status_message: string;
  error_message: string | null;

  // Generation parameters
  aspect_ratio: '16:9' | '16:10';
  duration_seconds: number;
  number_of_videos: number;

  // Generated content
  videos: VideoFile[];
  generated_prompt: string | null;

  // Metadata
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting video generation
 */
export interface StartVideoResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting video job status
 */
export interface VideoJobStatusResponse {
  success: boolean;
  job?: VideoJob;
  error?: string;
}

/**
 * Response from listing video jobs
 */
export interface ListVideoJobsResponse {
  success: boolean;
  jobs: VideoJob[];
  error?: string;
}

/**
 * Videos API
 */
export const videosAPI = {
  /**
   * Start video generation (background task)
   * Educational Note: Non-blocking - returns immediately with job_id
   * Uses Claude to generate optimized video prompt, then Google Veo for video
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string,
    aspectRatio: '16:9' | '16:10' = '16:9',
    durationSeconds: number = 8,
    numberOfVideos: number = 1
  ): Promise<StartVideoResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/videos`,
        {
          source_id: sourceId,
          direction: direction || '',
          aspect_ratio: aspectRatio,
          duration_seconds: durationSeconds,
          number_of_videos: numberOfVideos,
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start video generation');
      throw error;
    }
  },

  /**
   * Get video job status
   */
  async getJobStatus(projectId: string, jobId: string): Promise<VideoJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/videos/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get video job status');
      throw error;
    }
  },

  /**
   * List all video jobs for a project, optionally filtered by source
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListVideoJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/videos`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list video jobs');
      throw error;
    }
  },

  /**
   * Get the preview URL for a video (streams video in browser)
   */
  getPreviewUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/videos/${jobId}/preview/${filename}`;
  },

  /**
   * Get the download URL for a video
   */
  getDownloadUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/videos/${jobId}/download/${filename}`;
  },

  /**
   * Poll video job status until complete or error
   * Educational Note: Video generation can take 10-20 minutes with Google Veo
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: VideoJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 600  // Up to 20 minutes with 2s polling
  ): Promise<VideoJob> {
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

      if (attempts > 5 && currentInterval < 10000) {
        currentInterval = Math.min(currentInterval * 1.2, 10000);
      }
    }

    throw new Error('Video generation timed out');
  },
};
