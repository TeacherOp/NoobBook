/**
 * Business Reports API
 * Educational Note: Handles AI-generated data-driven business reports.
 * Business reports combine written analysis with data visualizations from CSV sources.
 * Uses multi-agent orchestration (business_report_agent + csv_analyzer_agent).
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-business-reports-api');

/**
 * Business report types available for generation
 */
export type BusinessReportType =
  | 'executive_summary'
  | 'financial_report'
  | 'performance_analysis'
  | 'market_research'
  | 'operations_report'
  | 'sales_report'
  | 'quarterly_review'
  | 'annual_report';

/**
 * Report section from planning phase
 */
export interface ReportSection {
  title: string;
  description: string;
  data_needs?: string[];
}

/**
 * Analysis result from CSV data
 */
export interface ReportAnalysis {
  query: string;
  summary: string;
  chart_paths: string[];
  section_context: string;
}

/**
 * Chart info from data analysis
 */
export interface ReportChart {
  filename: string;
  title: string;
  section: string;
  url: string;
}

/**
 * Business report generation job
 */
export interface BusinessReportJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  report_type: BusinessReportType;
  csv_source_ids: string[];
  context_source_ids: string[];
  focus_areas: string[];
  status: JobStatus;
  status_message: string;
  error_message: string | null;
  // Report plan fields
  title: string | null;
  executive_summary: string | null;
  sections: ReportSection[];
  // Data analysis tracking
  analyses: ReportAnalysis[];
  charts: ReportChart[];
  // Generated content
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
 * Response from starting business report generation
 */
export interface StartBusinessReportResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting business report job status
 */
export interface BusinessReportJobStatusResponse {
  success: boolean;
  job?: BusinessReportJob;
  error?: string;
}

/**
 * Response from listing business report jobs
 */
export interface ListBusinessReportJobsResponse {
  success: boolean;
  jobs: BusinessReportJob[];
  error?: string;
}

/**
 * Business Reports API
 */
export const businessReportsAPI = {
  /**
   * Start business report generation via business report agent
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string,
    reportType?: BusinessReportType,
    csvSourceIds?: string[],
    contextSourceIds?: string[],
    focusAreas?: string[]
  ): Promise<StartBusinessReportResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/business-report`,
        {
          source_id: sourceId,
          direction: direction || '',
          report_type: reportType || 'executive_summary',
          csv_source_ids: csvSourceIds || [],
          context_source_ids: contextSourceIds || [],
          focus_areas: focusAreas || [],
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start business report generation');
      throw error;
    }
  },

  /**
   * Get the status of a business report job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<BusinessReportJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/business-report-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get business report job status');
      throw error;
    }
  },

  /**
   * List all business report jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListBusinessReportJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/business-report-jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list business report jobs');
      throw error;
    }
  },

  /**
   * Delete a business report job
   */
  async deleteJob(projectId: string, jobId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await axios.delete(
        `${API_BASE_URL}/projects/${projectId}/studio/business-report-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to delete business report job');
      throw error;
    }
  },

  /**
   * Get the full URL for a business report file (markdown)
   */
  getFileUrl(projectId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/business-reports/${filename}`;
  },

  /**
   * Get the preview URL for a business report (returns markdown content)
   */
  getPreviewUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/business-reports/${jobId}/preview`;
  },

  /**
   * Get the download URL for a business report (ZIP with markdown + charts)
   */
  getDownloadUrl(projectId: string, jobId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/business-reports/${jobId}/download`;
  },

  /**
   * Get URL for a chart image (from ai_outputs/images/)
   */
  getChartUrl(projectId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/ai-images/${filename}`;
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
      log.error({ err: error }, 'failed to fetch business report preview');
      throw error;
    }
  },

  /**
   * Poll business report job status until complete or error
   * Educational Note: Added initial delay to avoid race condition where
   * the job might not be saved to disk yet when polling starts.
   * Business reports can take longer due to multiple CSV analyses.
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: BusinessReportJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 200 // Business reports with multiple analyses can take longer
  ): Promise<BusinessReportJob> {
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

    throw new Error('Business report generation timed out');
  },
};
