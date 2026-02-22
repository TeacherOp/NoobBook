/**
 * Websites API
 * Educational Note: Handles AI-generated multi-page websites.
 * Uses an agentic approach for complex multi-file generation.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-websites-api');

/**
 * Website page information
 */
export interface WebsitePage {
  filename: string;
  page_title: string;
  description: string;
}

/**
 * Website design system
 */
export interface WebsiteDesignSystem {
  primary_color: string;
  secondary_color: string;
  accent_color?: string;
  background_color: string;
  text_color: string;
  font_family: string;
}

/**
 * Generated website image
 */
export interface WebsiteImage {
  purpose: string;
  filename: string;
  placeholder: string;
  url: string;
}

/**
 * Website generation job
 */
export interface WebsiteJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  status_message: string;
  error_message: string | null;

  // Plan
  site_type: 'portfolio' | 'business' | 'blog' | 'landing' | 'corporate' | 'personal' | 'ecommerce' | null;
  site_name: string | null;
  pages: WebsitePage[];
  features: string[];
  design_system: WebsiteDesignSystem | null;
  navigation_style: 'fixed' | 'sticky' | 'static' | null;
  images_needed: Array<{
    purpose: string;
    description: string;
    aspect_ratio: string;
  }>;
  layout_notes: string | null;

  // Generated content
  images: WebsiteImage[];
  files: string[];
  pages_created: string[];
  features_implemented: string[];
  cdn_libraries_used: string[];
  summary: string | null;

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
 * Response from starting website generation
 */
export interface StartWebsiteResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting website job status
 */
export interface WebsiteJobStatusResponse {
  success: boolean;
  job?: WebsiteJob;
  error?: string;
}

/**
 * Response from listing website jobs
 */
export interface ListWebsiteJobsResponse {
  success: boolean;
  jobs: WebsiteJob[];
  error?: string;
}

/**
 * Websites API
 */
export const websitesAPI = {
  /**
   * Start website generation (background task)
   * Educational Note: Non-blocking - returns immediately with job_id
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartWebsiteResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/website`,
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
      log.error({ err: error }, 'failed to start website generation');
      throw error;
    }
  },

  /**
   * Get website job status
   */
  async getJobStatus(projectId: string, jobId: string): Promise<WebsiteJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/website-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get website job status');
      throw error;
    }
  },

  /**
   * List all website jobs for a project, optionally filtered by source
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListWebsiteJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/website-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list website jobs');
      throw error;
    }
  },

  /**
   * Get the preview URL for a website (opens in new window)
   */
  getPreviewUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/websites/${jobId}/preview`;
  },

  /**
   * Get the download URL for a website (ZIP with all files)
   */
  getDownloadUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/websites/${jobId}/download`;
  },

  /**
   * Poll website job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: WebsiteJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 200  // Websites can take longer (multi-file, iterative)
  ): Promise<WebsiteJob> {
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

    throw new Error('Website generation timed out');
  },
};
