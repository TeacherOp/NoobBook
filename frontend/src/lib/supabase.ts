/**
 * Supabase Client Configuration
 *
 * Educational Note: This module configures the Supabase client for the frontend.
 * The client is used for Realtime subscriptions to get instant updates on
 * source processing status and studio job progress without polling.
 *
 * IMPORTANT: Only the anon key is used here. The service role key should
 * NEVER be exposed to the frontend.
 */

import { createClient, SupabaseClient, RealtimeChannel } from '@supabase/supabase-js';

// Environment variables for Supabase connection
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

// Check if Supabase is configured
export const isSupabaseConfigured = (): boolean => {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
};

// Lazy-initialized Supabase client
let supabaseClient: SupabaseClient | null = null;

/**
 * Get or create the Supabase client singleton
 *
 * Educational Note: We use lazy initialization to avoid errors when
 * Supabase is not configured (e.g., in local development without Supabase).
 */
export const getSupabase = (): SupabaseClient | null => {
  if (!isSupabaseConfigured()) {
    return null;
  }

  if (!supabaseClient) {
    supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      realtime: {
        params: {
          eventsPerSecond: 10,
        },
      },
    });
  }

  return supabaseClient;
};

/**
 * Subscribe to a specific table for realtime changes
 *
 * Educational Note: Supabase Realtime uses PostgreSQL's LISTEN/NOTIFY
 * under the hood. When a row changes, PostgreSQL emits an event that
 * the Realtime server broadcasts to subscribed clients via WebSocket.
 */
export const subscribeToTable = (
  table: string,
  filter: string,
  callback: (payload: unknown) => void
): RealtimeChannel | null => {
  const supabase = getSupabase();
  if (!supabase) return null;

  const channel = supabase
    .channel(`${table}_changes`)
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table,
        filter,
      },
      callback
    )
    .subscribe();

  return channel;
};

/**
 * Unsubscribe from a Realtime channel
 */
export const unsubscribe = (channel: RealtimeChannel): void => {
  const supabase = getSupabase();
  if (supabase && channel) {
    supabase.removeChannel(channel);
  }
};

export { type RealtimeChannel };
