/**
 * useSourceStatus Hook - Real-time source processing status updates
 *
 * Educational Note: This hook replaces polling with Supabase Realtime
 * subscriptions. When a source's status changes in the database
 * (uploaded -> processing -> embedding -> ready), the frontend
 * receives instant updates via WebSocket.
 *
 * Usage:
 *   const { sources, isConnected } = useSourceStatus(projectId);
 *
 * Features:
 * - Falls back to polling if Supabase is not configured
 * - Automatically reconnects on connection loss
 * - Provides connection status for UI feedback
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getSupabase,
  isSupabaseConfigured,
  type RealtimeChannel,
} from '../lib/supabase';
import { sourcesAPI, type Source } from '../lib/api/sources';

interface SourceStatusUpdate {
  id: string;
  status: Source['status'];
  processing_info?: Record<string, unknown>;
  embedding_info?: Record<string, unknown>;
  updated_at: string;
}

interface UseSourceStatusResult {
  sources: Source[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

// Polling interval when Supabase Realtime is not available (5 seconds)
const POLLING_INTERVAL = 5000;

/**
 * Hook to subscribe to source status updates for a project
 */
export function useSourceStatus(projectId: string | null): UseSourceStatusResult {
  const [sources, setSources] = useState<Source[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const channelRef = useRef<RealtimeChannel | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch all sources from the API
  const fetchSources = useCallback(async () => {
    if (!projectId) {
      setSources([]);
      setIsLoading(false);
      return;
    }

    try {
      const fetchedSources = await sourcesAPI.listSources(projectId);
      setSources(fetchedSources);
      setError(null);
    } catch (err) {
      console.error('Error fetching sources:', err);
      setError('Failed to load sources');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Handle realtime source updates
  const handleSourceUpdate = useCallback((payload: unknown) => {
    const data = payload as {
      eventType: string;
      new?: SourceStatusUpdate;
      old?: { id: string };
    };

    setSources((prevSources) => {
      switch (data.eventType) {
        case 'INSERT':
          if (data.new) {
            // Fetch full source data since realtime only sends changed columns
            fetchSources();
          }
          return prevSources;

        case 'UPDATE':
          if (data.new) {
            return prevSources.map((source) =>
              source.id === data.new!.id
                ? {
                    ...source,
                    status: data.new!.status,
                    processing_info: data.new!.processing_info ?? source.processing_info,
                    embedding_info: data.new!.embedding_info ?? source.embedding_info,
                    updated_at: data.new!.updated_at,
                  }
                : source
            );
          }
          return prevSources;

        case 'DELETE':
          if (data.old) {
            return prevSources.filter((source) => source.id !== data.old!.id);
          }
          return prevSources;

        default:
          return prevSources;
      }
    });
  }, [fetchSources]);

  // Set up Supabase Realtime subscription
  useEffect(() => {
    if (!projectId) return;

    // Initial fetch
    fetchSources();

    // Check if Supabase is configured
    if (!isSupabaseConfigured()) {
      console.log('Supabase not configured, falling back to polling');
      // Fall back to polling
      pollingIntervalRef.current = setInterval(fetchSources, POLLING_INTERVAL);
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }

    const supabase = getSupabase();
    if (!supabase) return;

    // Subscribe to sources table changes for this project
    const channel = supabase
      .channel(`sources:${projectId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'sources',
          filter: `project_id=eq.${projectId}`,
        },
        handleSourceUpdate
      )
      .subscribe((status) => {
        console.log('Source subscription status:', status);
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
  }, [projectId, fetchSources, handleSourceUpdate]);

  return {
    sources,
    isConnected,
    isLoading,
    error,
    refresh: fetchSources,
  };
}
