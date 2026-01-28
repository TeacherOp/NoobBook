/**
 * Hooks Index
 *
 * Educational Note: Central export for all custom React hooks.
 * Hooks encapsulate reusable stateful logic for React components.
 */

// Mobile detection
export { useIsMobile } from './use-mobile';

// Supabase Realtime hooks for instant updates
export { useSourceStatus } from './use-source-status';
export {
  useStudioJobStatus,
  useProjectStudioJobs,
  type StudioJob,
  type StudioJobStatus,
} from './use-studio-job-status';
export {
  useTaskStatus,
  useTargetTasks,
  type BackgroundTask,
  type TaskStatus,
} from './use-task-status';
