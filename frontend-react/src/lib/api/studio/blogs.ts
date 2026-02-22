/**
 * Blog Posts API
 * Educational Note: Handles AI-generated comprehensive blog posts with images.
 * Blog posts are SEO-optimized and stored as markdown files with images.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-blogs-api');

/**
 * Blog types available for generation
 */
export type BlogType =
  | 'case_study'
  | 'listicle'
  | 'how_to_guide'
  | 'opinion'
  | 'product_review'
  | 'news'
  | 'tutorial'
  | 'comparison'
  | 'interview'
  | 'roundup';

/**
 * Blog outline section from planning phase
 */
export interface BlogOutlineSection {
  heading: string;
  content_description: string;
  subsections?: string[];
  needs_image: boolean;
  image_description?: string;
}

/**
 * Generated blog image info
 */
export interface BlogImage {
  purpose: string;
  section_heading: string;
  filename: string;
  placeholder: string;
  alt_text: string;
  url: string;
}

/**
 * Blog post generation job
 */
export interface BlogJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  target_keyword: string;
  blog_type: BlogType;
  status: JobStatus;
  status_message: string;
  error_message: string | null;
  // Blog plan fields
  title: string | null;
  meta_description: string | null;
  outline: BlogOutlineSection[];
  target_word_count: number;
  tone: string | null;
  // Generated content
  images: BlogImage[];
  markdown_file: string | null;
  markdown_url: string | null;
  preview_url: string | null;
  word_count: number | null;
  // Metadata
  iterations: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting blog post generation
 */
export interface StartBlogResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting blog job status
 */
export interface BlogJobStatusResponse {
  success: boolean;
  job?: BlogJob;
  error?: string;
}

/**
 * Response from listing blog jobs
 */
export interface ListBlogJobsResponse {
  success: boolean;
  jobs: BlogJob[];
  error?: string;
}

/**
 * Blog Posts API
 */
export const blogsAPI = {
  /**
   * Start blog post generation via blog agent
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string,
    targetKeyword?: string,
    blogType?: BlogType
  ): Promise<StartBlogResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/blog`,
        {
          source_id: sourceId,
          direction: direction || '',
          target_keyword: targetKeyword || '',
          blog_type: blogType || 'how_to_guide',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start blog post generation');
      throw error;
    }
  },

  /**
   * Get the status of a blog post job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<BlogJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/blog-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get blog job status');
      throw error;
    }
  },

  /**
   * List all blog post jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListBlogJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/blog-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list blog jobs');
      throw error;
    }
  },

  /**
   * Delete a blog post job
   */
  async deleteJob(projectId: string, jobId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await axios.delete(
        `${API_BASE_URL}/projects/${projectId}/studio/blog-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to delete blog job');
      throw error;
    }
  },

  /**
   * Get the full URL for a blog file (markdown or image)
   * Routes through backend API which fetches from Supabase Storage
   */
  getFileUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/blogs/${jobId}/${filename}`;
  },

  /**
   * Get the preview URL for a blog post (returns markdown content)
   */
  getPreviewUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/blogs/${jobId}/preview`;
  },

  /**
   * Get the download URL for a blog post (ZIP with markdown + images)
   */
  getDownloadUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/blogs/${jobId}/download`;
  },

  /**
   * Fetch markdown preview content directly
   */
  async getPreview(projectId: string, jobId: string): Promise<string> {
    try {
      const response = await axios.get(this.getPreviewUrl(projectId, jobId), {
        responseType: 'text',
      });
      return response.data;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch blog preview');
      throw error;
    }
  },

  /**
   * Poll blog job status until complete or error
   * Educational Note: Added initial delay to avoid race condition where
   * the job might not be saved to disk yet when polling starts.
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: BlogJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 150 // Blog posts can take longer with images
  ): Promise<BlogJob> {
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

    throw new Error('Blog post generation timed out');
  },
};
