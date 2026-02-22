/**
 * Email Templates API
 * Educational Note: Handles AI-generated HTML email templates with images.
 * Uses an agentic approach for multi-step generation.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-emails-api');

/**
 * Email template section plan
 */
export interface EmailSection {
  section_type: 'header' | 'hero' | 'content' | 'product_grid' | 'cta' | 'testimonial' | 'footer';
  section_name: string;
  content_description: string;
  needs_image: boolean;
  image_description?: string;
}

/**
 * Email template color scheme
 */
export interface EmailColorScheme {
  primary: string;
  secondary: string;
  background: string;
  text: string;
  button: string;
}

/**
 * Generated email image info
 */
export interface EmailImage {
  section_name: string;
  filename: string;
  placeholder: string;
  url: string;
}

/**
 * Email template generation job
 */
export interface EmailJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  status_message: string;
  error_message: string | null;
  // Template plan
  template_name: string | null;
  template_type: 'newsletter' | 'promotional' | 'transactional' | 'announcement' | null;
  color_scheme: EmailColorScheme | null;
  sections: EmailSection[];
  layout_notes: string | null;
  // Generated content
  images: EmailImage[];
  html_file: string | null;
  html_url: string | null;
  preview_url: string | null;
  subject_line: string | null;
  preheader_text: string | null;
  // Metadata
  iterations: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting email template generation
 */
export interface StartEmailResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting email job status
 */
export interface EmailJobStatusResponse {
  success: boolean;
  job?: EmailJob;
  error?: string;
}

/**
 * Response from listing email jobs
 */
export interface ListEmailJobsResponse {
  success: boolean;
  jobs: EmailJob[];
  error?: string;
}

/**
 * Email Templates API
 */
export const emailsAPI = {
  /**
   * Start email template generation via email agent
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartEmailResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/email-template`,
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
      log.error({ err: error }, 'failed to start email template generation');
      throw error;
    }
  },

  /**
   * Get the status of an email template job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<EmailJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/email-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get email job status');
      throw error;
    }
  },

  /**
   * List all email template jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListEmailJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/email-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list email jobs');
      throw error;
    }
  },

  /**
   * Get the full URL for an email template file (HTML or image)
   */
  getFileUrl(projectId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/email-templates/${filename}`;
  },

  /**
   * Get the preview URL for an email template
   */
  getPreviewUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/email-templates/${jobId}/preview`;
  },

  /**
   * Get the download URL for an email template (ZIP)
   */
  getDownloadUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/email-templates/${jobId}/download`;
  },

  /**
   * Poll email job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: EmailJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 150  // Email generation can take longer (agentic)
  ): Promise<EmailJob> {
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

    throw new Error('Email template generation timed out');
  },
};
