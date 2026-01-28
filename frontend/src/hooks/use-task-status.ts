/**
 * useTaskStatus Hook - Real-time background task status updates
 *
 * Educational Note: Background tasks are used for long-running operations
 * like source processing, embedding generation, and research agent execution.
 * This hook provides instant updates on task progress via Supabase Realtime.
 *
 * Usage:
 *   const { task, isConnected } = useTaskStatus(taskId);
 *
 * Task Types:
 * - source_processing: Extract text from uploaded files
 * - source_embedding: Generate vector embeddings for search
 * - research_agent: Deep research on a topic
 * - chat_naming: Auto-generate chat titles
 * - memory_merge: Merge user/project memory
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getSupabase,
  isSupabaseConfigured,
  type RealtimeChannel,
} from '../lib/supabase';

/**
 * Background task status type
 */
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

/**
 * Background task data structure
 */
export interface BackgroundTask {
  id: string;
  task_type: string;
  target_id: string;
  status: TaskStatus;
  progress?: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface UseTaskStatusResult {
  task: BackgroundTask | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

// Polling interval when Supabase Realtime is not available (2 seconds)
const POLLING_INTERVAL = 2000;

// Backend API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api/v1';

/**
 * Hook to subscribe to a specific background task's status
 */
export function useTaskStatus(taskId: string | null): UseTaskStatusResult {
  const [task, setTask] = useState<BackgroundTask | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const channelRef = useRef<RealtimeChannel | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch task status from the API
  const fetchTask = useCallback(async () => {
    if (!taskId) {
      setTask(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch task status');
      }
      const data = await response.json();
      setTask(data.task);
      setError(null);

      // Stop polling if task is complete
      const finalStatuses: TaskStatus[] = ['completed', 'failed', 'cancelled'];
      if (finalStatuses.includes(data.task.status)) {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error fetching task:', err);
      setError('Failed to load task status');
    } finally {
      setIsLoading(false);
    }
  }, [taskId]);

  // Handle realtime task updates
  const handleTaskUpdate = useCallback((payload: unknown) => {
    const data = payload as {
      eventType: string;
      new?: BackgroundTask;
    };

    if (data.eventType === 'UPDATE' && data.new) {
      setTask((prevTask) => {
        if (!prevTask || prevTask.id !== data.new!.id) return prevTask;
        return {
          ...prevTask,
          ...data.new,
        };
      });
    }
  }, []);

  // Set up Supabase Realtime subscription
  useEffect(() => {
    if (!taskId) return;

    // Initial fetch
    fetchTask();

    // Check if Supabase is configured
    if (!isSupabaseConfigured()) {
      console.log('Supabase not configured, falling back to polling for tasks');
      // Fall back to polling
      pollingIntervalRef.current = setInterval(fetchTask, POLLING_INTERVAL);
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }

    const supabase = getSupabase();
    if (!supabase) return;

    // Subscribe to this specific task
    const channel = supabase
      .channel(`task:${taskId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'tasks',
          filter: `id=eq.${taskId}`,
        },
        handleTaskUpdate
      )
      .subscribe((status) => {
        console.log('Task subscription status:', status);
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
  }, [taskId, fetchTask, handleTaskUpdate]);

  return {
    task,
    isConnected,
    isLoading,
    error,
  };
}

/**
 * Hook to subscribe to all tasks for a specific target (e.g., source_id)
 */
export function useTargetTasks(targetId: string | null): {
  tasks: BackgroundTask[];
  activeTasks: BackgroundTask[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
} {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const channelRef = useRef<RealtimeChannel | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch all tasks for the target
  const fetchTasks = useCallback(async () => {
    if (!targetId) {
      setTasks([]);
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/tasks?target_id=${targetId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch tasks');
      }
      const data = await response.json();
      setTasks(data.tasks || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching tasks:', err);
      setError('Failed to load tasks');
    } finally {
      setIsLoading(false);
    }
  }, [targetId]);

  // Handle realtime task updates
  const handleTasksUpdate = useCallback((payload: unknown) => {
    const data = payload as {
      eventType: string;
      new?: BackgroundTask;
      old?: { id: string };
    };

    setTasks((prevTasks) => {
      switch (data.eventType) {
        case 'INSERT':
          if (data.new) {
            return [...prevTasks, data.new];
          }
          return prevTasks;

        case 'UPDATE':
          if (data.new) {
            return prevTasks.map((task) =>
              task.id === data.new!.id ? { ...task, ...data.new } : task
            );
          }
          return prevTasks;

        case 'DELETE':
          if (data.old) {
            return prevTasks.filter((task) => task.id !== data.old!.id);
          }
          return prevTasks;

        default:
          return prevTasks;
      }
    });
  }, []);

  // Set up subscription
  useEffect(() => {
    if (!targetId) return;

    fetchTasks();

    if (!isSupabaseConfigured()) {
      pollingIntervalRef.current = setInterval(fetchTasks, POLLING_INTERVAL);
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }

    const supabase = getSupabase();
    if (!supabase) return;

    const channel = supabase
      .channel(`tasks:${targetId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'tasks',
          filter: `target_id=eq.${targetId}`,
        },
        handleTasksUpdate
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
  }, [targetId, fetchTasks, handleTasksUpdate]);

  // Filter active tasks (pending or running)
  const activeTasks = tasks.filter(
    (task) => task.status === 'pending' || task.status === 'running'
  );

  return {
    tasks,
    activeTasks,
    isConnected,
    isLoading,
    error,
  };
}
