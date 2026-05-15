/**
 * Saved Insights API client.
 *
 * Saved insights are chat prompts the user marks to auto-refresh on a
 * daily or weekly cadence. The backend scheduler re-runs them; this
 * client surfaces list/create/delete/refresh for the Studio panel UI.
 */
import axios from 'axios';
import { API_BASE_URL } from './client';
import { createLogger } from '@/lib/logger';

const log = createLogger('insights-api');

export type InsightCadence = 'daily' | 'weekly';

export interface SavedInsight {
  id: string;
  project_id: string;
  owner_user_id: string;
  title: string;
  prompt: string;
  cadence: InsightCadence;
  last_run_at: string | null;
  last_result: string | null;
  last_chat_id: string | null;
  last_error: string | null;
  is_running: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateInsightInput {
  title?: string;
  prompt: string;
  cadence: InsightCadence;
}

export const insightsAPI = {
  async list(projectId: string): Promise<SavedInsight[]> {
    try {
      const { data } = await axios.get(`${API_BASE_URL}/projects/${projectId}/insights`);
      return data?.insights ?? [];
    } catch (err) {
      log.error({ err }, 'failed to list insights');
      return [];
    }
  },

  async create(projectId: string, input: CreateInsightInput): Promise<SavedInsight | null> {
    try {
      const { data } = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/insights`,
        input,
      );
      return data?.insight ?? null;
    } catch (err) {
      log.error({ err }, 'failed to create insight');
      throw err;
    }
  },

  async remove(projectId: string, insightId: string): Promise<boolean> {
    try {
      await axios.delete(`${API_BASE_URL}/projects/${projectId}/insights/${insightId}`);
      return true;
    } catch (err) {
      log.error({ err }, 'failed to delete insight');
      return false;
    }
  },

  /**
   * Kick a manual refresh. Returns immediately (202); poll list() for the
   * updated row to see the new result land.
   */
  async refresh(projectId: string, insightId: string): Promise<boolean> {
    try {
      await axios.post(
        `${API_BASE_URL}/projects/${projectId}/insights/${insightId}/refresh`,
      );
      return true;
    } catch (err) {
      log.error({ err }, 'failed to refresh insight');
      return false;
    }
  },
};
