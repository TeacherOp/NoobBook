/**
 * Projects API Service
 * Educational Note: These methods abstract the API calls for project management,
 * making them easier to use throughout the application and maintaining consistency.
 */

import type { AxiosRequestConfig } from 'axios';
import { api } from './client';

/**
 * Memory Types
 * Educational Note: Memory helps the AI maintain context across conversations.
 * User memory persists across all projects, project memory is specific to a project.
 */
export interface MemoryData {
  user_memory: string | null;
  project_memory: string | null;
}

/**
 * Cost Tracking Types
 * Educational Note: These types match the backend cost tracking structure.
 */
export interface ModelCostBreakdown {
  input_tokens: number;
  output_tokens: number;
  cost: number;
  /** Anthropic prompt-cache tokens written. Billed at 1.25× input. */
  cache_creation_tokens?: number;
  /** Anthropic prompt-cache tokens read back. Billed at 0.10× input. */
  cache_read_tokens?: number;
}

export interface CostTracking {
  total_cost: number;
  by_model: {
    opus: ModelCostBreakdown;
    sonnet: ModelCostBreakdown;
    haiku: ModelCostBreakdown;
  };
  /** Net dollars saved via prompt caching (vs. uncached counterfactual). */
  cache_savings?: number;
  /** Image-generation usage, keyed by model. Always optional. */
  images?: Record<string, {
    count: number;
    cost: number;
    by_size_quality?: Record<string, { count: number; cost: number }>;
  }>;
}

/**
 * Project API Methods
 */
export const projectsAPI = {
  // List all projects. Config (e.g. AbortController signal) is forwarded so
  // callers can cancel an in-flight load — particularly important now that
  // the api-client interceptor silently retries transient failures for ~7s,
  // long enough that a user could navigate away mid-retry.
  list: (config?: AxiosRequestConfig) => api.get('/projects', config),

  // Create a new project
  create: (data: { name: string; description?: string }) =>
    api.post('/projects', data),

  // Get a specific project
  get: (id: string) => api.get(`/projects/${id}`),

  // Update a project
  update: (id: string, data: { name?: string; description?: string }) =>
    api.put(`/projects/${id}`, data),

  // Delete a project
  delete: (id: string) => api.delete(`/projects/${id}`),

  // Open a project (mark as accessed)
  open: (id: string) => api.post(`/projects/${id}/open`),

  // Get project cost tracking data
  getCosts: (id: string) => api.get(`/projects/${id}/costs`),

  // Get project memory data (user memory + project memory)
  getMemory: (id: string) => api.get(`/projects/${id}/memory`),

  // Update user and/or project memory (both fields optional)
  updateMemory: (id: string, data: { user_memory?: string; project_memory?: string }) =>
    api.put(`/projects/${id}/memory`, data),
};
