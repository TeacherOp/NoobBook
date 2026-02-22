/**
 * Audio Overview API
 * Educational Note: Handles audio overview generation using ElevenLabs TTS.
 * Non-blocking pattern - returns job_id for polling.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-audio-api');

/**
 * Audio job status (alias for backwards compatibility)
 */
export type AudioJobStatus = JobStatus;

/**
 * Audio job record from the API
 */
export interface AudioJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: AudioJobStatus;
  progress: string;
  error: string | null;
  audio_path: string | null;
  audio_filename: string | null;
  audio_url: string | null;
  script_path: string | null;
  audio_info: {
    file_size_bytes?: number;
    estimated_duration_seconds?: number;
    word_count?: number;
    voice_id?: string;
    model_id?: string;
  } | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting audio generation
 */
export interface StartAudioResponse {
  success: boolean;
  job_id?: string;
  message?: string;
  source_name?: string;
  error?: string;
}

/**
 * Response from getting job status
 */
export interface AudioJobStatusResponse {
  success: boolean;
  job?: AudioJob;
  error?: string;
}

/**
 * Response from listing jobs
 */
export interface ListAudioJobsResponse {
  success: boolean;
  jobs: AudioJob[];
  count: number;
  error?: string;
}

/**
 * TTS configuration status
 */
export interface TTSStatusResponse {
  success: boolean;
  configured: boolean;
  error?: string;
}

/**
 * Audio Overview API
 */
export const audioAPI = {
  /**
   * Start audio overview generation
   * Educational Note: Non-blocking - returns immediately with job_id
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string
  ): Promise<StartAudioResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/audio-overview`,
        {
          source_id: sourceId,
          direction: direction || 'Create an engaging audio overview of this content.',
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start audio generation');
      throw error;
    }
  },

  /**
   * Get the status of an audio generation job
   */
  async getJobStatus(projectId: string, jobId: string): Promise<AudioJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get job status');
      throw error;
    }
  },

  /**
   * List all audio jobs for a project
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListAudioJobsResponse> {
    try {
      const params = sourceId ? { source_id: sourceId } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/jobs`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to list jobs');
      throw error;
    }
  },

  /**
   * Check if TTS (ElevenLabs) is configured
   */
  async checkTTSStatus(): Promise<TTSStatusResponse> {
    try {
      const response = await axios.get(`${API_BASE_URL}/studio/tts/status`);
      return response.data;
    } catch (error) {
      log.error({ err: error }, 'failed to check TTS status');
      return { success: false, configured: false };
    }
  },

  /**
   * Get the full URL for an audio file
   */
  getAudioUrl(projectId: string, jobId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/audio/${jobId}/${filename}`;
  },

  /**
   * Poll job status until complete or error
   * Educational Note: Uses polling with exponential backoff
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: AudioJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 120
  ): Promise<AudioJob> {
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

    throw new Error('Audio generation timed out');
  },
};
