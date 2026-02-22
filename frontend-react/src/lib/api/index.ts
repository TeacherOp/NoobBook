/**
 * API Module - Central exports for all API services
 * Educational Note: This file provides a single import point for all API functionality.
 *
 * Import patterns:
 *   import { api, projectsAPI } from '@/lib/api';
 *   import { audioAPI, websitesAPI, JobStatus } from '@/lib/api/studio';
 */

// Core API client
export { api, API_BASE_URL } from './client';

// Auth API
export { authAPI } from './auth';

// Projects API
export { projectsAPI } from './projects';
export type { MemoryData, ModelCostBreakdown, CostTracking } from './projects';

// Feature APIs (re-export for convenience)
export * from './chats';
export * from './settings';
export * from './sources';
export * from './brand';

// Studio APIs are accessed via '@/lib/api/studio' for better organization
// Example: import { audioAPI } from '@/lib/api/studio';
