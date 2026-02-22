/**
 * Projects API Service
 * Educational Note: These methods abstract the API calls for project management,
 * making them easier to use throughout the application and maintaining consistency.
 */

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
}

export interface CostTracking {
  total_cost: number;
  by_model: {
    sonnet: ModelCostBreakdown;
    haiku: ModelCostBreakdown;
  };
}

/**
 * Project API Methods
 */
export const projectsAPI = {
  // List all projects
  list: () => api.get('/projects'),

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
