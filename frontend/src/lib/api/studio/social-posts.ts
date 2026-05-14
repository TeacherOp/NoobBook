/**
 * Social Posts API
 * Educational Note: Handles AI-generated social media posts with images.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { listStudioJobsByType } from './jobGroups';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-social-posts-api');

/**
 * Social post image info
 */
export interface SocialPostImage {
  filename: string;
  path: string;
  index: number;
}

/**
 * Single social post for one platform
 */
export interface SocialPost {
  platform: 'linkedin' | 'instagram' | 'twitter';
  copy: string;
  hashtags: string[];
  aspect_ratio: string;
  image_prompt: string;
  image: SocialPostImage | null;
  image_url: string | null;
}

/**
 * Social post job record from the API
 */
export interface SocialPostJob {
  id: string;
  topic: string;
  direction: string;
  platforms?: string[];
  status: JobStatus;
  progress: string;
  error: string | null;
  posts: SocialPost[];
  topic_summary: string | null;
  post_count: number;
  generation_time_seconds: number | null;
  // Edit lineage
  parent_job_id: string | null;
  edit_instructions: string | null;
  // Metadata
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting social post generation
 */
export interface StartSocialPostsResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  topic?: string;
  error?: string;
}

/**
 * Response from getting social post job status
 */
export interface SocialPostJobStatusResponse {
  success: boolean;
  job?: SocialPostJob;
  error?: string;
}

/**
 * Response from listing social post jobs
 */
export interface ListSocialPostJobsResponse {
  success: boolean;
  jobs: SocialPostJob[];
  count: number;
  error?: string;
}

/**
 * Social Posts API
 */
export const socialPostsAPI = {
  /**
   * Start social post generation
   */
  async startGeneration(
    projectId: string,
    topic: string,
    direction?: string,
    platforms?: string[],
    logoSource?: 'auto' | 'brand_icon' | 'source' | 'none',
    logoSourceId?: string,
    parentJobId?: string,
    editInstructions?: string,
    sourceIds?: string[]
  ): Promise<StartSocialPostsResponse> {
    try {
      const body: Record<string, unknown> = {
        topic,
        direction: direction || 'Create engaging social media posts for this topic.',
        ...(platforms && { platforms }),
        logo_source: logoSource || 'auto',
      };
      if (logoSourceId) body.logo_source_id = logoSourceId;
      if (parentJobId) body.parent_job_id = parentJobId;
      if (editInstructions) body.edit_instructions = editInstructions;
      if (sourceIds && sourceIds.length > 0) body.source_ids = sourceIds;

      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/social-posts`,
        body
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start social post generation');
      throw error;
    }
  },

  /**
   * Get the status of a social post job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<SocialPostJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/social-post-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get social post job status');
      throw error;
    }
  },

  /**
   * List all social post jobs for a project
   */
  async listJobs(projectId: string): Promise<ListSocialPostJobsResponse> {
    return listStudioJobsByType<SocialPostJob>(projectId, 'social_post');
  },

  /**
   * Delete a social post job
   */
  async deleteJob(projectId: string, jobId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await axios.delete(
        `${API_BASE_URL}/projects/${projectId}/studio/social-post-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to delete social post job');
      throw error;
    }
  },

  /**
   * Get the full URL for a social post image
   */
  getImageUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/social/${jobId}/${filename}`;
  },

  /**
   * Poll social post job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: SocialPostJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120
  ): Promise<SocialPostJob> {
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

      if (job.status === 'ready' || job.status === 'error' || job.status === 'cancelled') {
        return job;
      }

      await new Promise((resolve) => setTimeout(resolve, currentInterval));

      attempts++;

      if (attempts > 5 && currentInterval < 5000) {
        currentInterval = Math.min(currentInterval * 1.2, 5000);
      }
    }

    throw new Error('Social post generation timed out');
  },
};
