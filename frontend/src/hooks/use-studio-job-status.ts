/**
 * useStudioJobStatus Hook - Real-time studio job progress updates
 *
 * Educational Note: This hook provides instant updates on studio job
 * progress (audio generation, video creation, document exports, etc.)
 * via Supabase Realtime. Replaces the polling pattern previously used.
 *
 * Usage:
 *   const { job, isConnected } = useStudioJobStatus(jobId);
 *
 * Studio Job Types:
 * - audio_overview: Generate podcast-style audio
 * - video_overview: Generate video content
 * - presentation: Generate slide decks
 * - email_draft: Generate email content
 * - and 14 more job types...
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getSupabase,
  isSupabaseConfigured,
  type RealtimeChannel,
} from '../lib/supabase';

/**
 * Studio job status type
 * Educational Note: Jobs progress through these states:
 * - pending: Job created, waiting to start
 * - processing: AI is generating content
 * - completed: Content ready for download/view
 * - error: Generation failed
 */
export type StudioJobStatus = 'pending' | 'processing' | 'completed' | 'error';

/**
 * Studio job data structure
 */
export interface StudioJob {
  id: string;
  project_id: string;
  job_type: string;
  status: StudioJobStatus;
  input_data: Record<string, unknown>;
  output_paths: Record<string, string>;
  error_message?: string;
  progress?: number;
  created_at: string;
  updated_at: string;
}

interface UseStudioJobStatusResult {
  job: StudioJob | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

// Polling interval when Supabase Realtime is not available (3 seconds)
const POLLING_INTERVAL = 3000;

// Backend API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api/v1';

/**
 * Hook to subscribe to a specific studio job's status
 */
export function useStudioJobStatus(jobId: string | null): UseStudioJobStatusResult {
  const [job, setJob] = useState<StudioJob | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const channelRef = useRef<RealtimeChannel | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch job status from the API
  const fetchJob = useCallback(async () => {
    if (!jobId) {
      setJob(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/studio/jobs/${jobId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch job status');
      }
      const data = await response.json();
      setJob(data.job);
      setError(null);

      // Stop polling if job is complete or errored
      if (data.job.status === 'completed' || data.job.status === 'error') {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error fetching studio job:', err);
      setError('Failed to load job status');
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  // Handle realtime job updates
  const handleJobUpdate = useCallback((payload: unknown) => {
    const data = payload as {
      eventType: string;
      new?: StudioJob;
    };

    if (data.eventType === 'UPDATE' && data.new) {
      setJob((prevJob) => {
        if (!prevJob || prevJob.id !== data.new!.id) return prevJob;
        return {
          ...prevJob,
          ...data.new,
        };
      });
    }
  }, []);

  // Set up Supabase Realtime subscription
  useEffect(() => {
    if (!jobId) return;

    // Initial fetch
    fetchJob();

    // Check if Supabase is configured
    if (!isSupabaseConfigured()) {
      console.log('Supabase not configured, falling back to polling for studio jobs');
      // Fall back to polling
      pollingIntervalRef.current = setInterval(fetchJob, POLLING_INTERVAL);
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }

    const supabase = getSupabase();
    if (!supabase) return;

    // Subscribe to this specific studio job
    const channel = supabase
      .channel(`studio_job:${jobId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'studio_jobs',
          filter: `id=eq.${jobId}`,
        },
        handleJobUpdate
      )
      .subscribe((status) => {
        console.log('Studio job subscription status:', status);
        setIsConnected(status === 'SUBSCRIBED');
      });

    channelRef.current = channel;

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      setIsConnected(false);
    };
  }, [jobId, fetchJob, handleJobUpdate]);

  return {
    job,
    isConnected,
    isLoading,
    error,
  };
}

/**
 * Hook to subscribe to all studio jobs for a project
 */
export function useProjectStudioJobs(projectId: string | null): {
  jobs: StudioJob[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [jobs, setJobs] = useState<StudioJob[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const channelRef = useRef<RealtimeChannel | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch all jobs for the project
  const fetchJobs = useCallback(async () => {
    if (!projectId) {
      setJobs([]);
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}/studio/jobs`);
      if (!response.ok) {
        throw new Error('Failed to fetch studio jobs');
      }
      const data = await response.json();
      setJobs(data.jobs || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching studio jobs:', err);
      setError('Failed to load studio jobs');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Handle realtime job updates
  const handleJobsUpdate = useCallback((payload: unknown) => {
    const data = payload as {
      eventType: string;
      new?: StudioJob;
      old?: { id: string };
    };

    setJobs((prevJobs) => {
      switch (data.eventType) {
        case 'INSERT':
          if (data.new) {
            return [...prevJobs, data.new];
          }
          return prevJobs;

        case 'UPDATE':
          if (data.new) {
            return prevJobs.map((job) =>
              job.id === data.new!.id ? { ...job, ...data.new } : job
            );
          }
          return prevJobs;

        case 'DELETE':
          if (data.old) {
            return prevJobs.filter((job) => job.id !== data.old!.id);
          }
          return prevJobs;

        default:
          return prevJobs;
      }
    });
  }, []);

  // Set up subscription
  useEffect(() => {
    if (!projectId) return;

    fetchJobs();

    if (!isSupabaseConfigured()) {
      pollingIntervalRef.current = setInterval(fetchJobs, POLLING_INTERVAL);
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }

    const supabase = getSupabase();
    if (!supabase) return;

    const channel = supabase
      .channel(`studio_jobs:${projectId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'studio_jobs',
          filter: `project_id=eq.${projectId}`,
        },
        handleJobsUpdate
      )
      .subscribe((status) => {
        setIsConnected(status === 'SUBSCRIBED');
      });

    channelRef.current = channel;

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      setIsConnected(false);
    };
  }, [projectId, fetchJobs, handleJobsUpdate]);

  return {
    jobs,
    isConnected,
    isLoading,
    error,
    refresh: fetchJobs,
  };
}
