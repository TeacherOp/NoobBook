/**
 * useStudioGeneration
 * Shared composable for studio section generation pattern.
 * All 17 non-audio sections: load jobs, register handler, poll, show result.
 */
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import type { StudioSignal } from '@/lib/types/studio'
import { createLogger } from '@/lib/logger'

const log = createLogger('studio-generation')

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyJob = Record<string, any>

export interface UseStudioGenerationOptions {
  itemLabel: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  loadJobs: () => Promise<any[]>
  startGeneration: (signal: StudioSignal) => Promise<{ success: boolean; job_id?: string; error?: string }>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pollJobStatus: (jobId: string, onProgress: (job: any) => void) => Promise<any>
  onSuccess?: (job: AnyJob) => void
}

export function useStudioGeneration(options: UseStudioGenerationOptions) {
  const savedJobs = ref<AnyJob[]>([])
  const currentJob = ref<AnyJob | null>(null)
  const isGenerating = ref(false)
  const viewingJob = ref<AnyJob | null>(null)

  async function loadSavedJobs() {
    try {
      savedJobs.value = await options.loadJobs()
    } catch (err) {
      log.error({ err }, `failed to load ${options.itemLabel} jobs`)
    }
  }

  async function handleGeneration(signal: StudioSignal) {
    const sourceId = signal.sources[0]?.source_id
    if (!sourceId) { toast.error(`No source specified for ${options.itemLabel} generation.`); return }

    isGenerating.value = true
    currentJob.value = null
    try {
      const start = await options.startGeneration(signal)
      if (!start.success || !start.job_id) {
        toast.error(start.error || `Failed to start ${options.itemLabel} generation.`)
        return
      }
      toast.success(`Generating ${options.itemLabel}...`)
      const finalJob = await options.pollJobStatus(start.job_id, job => { currentJob.value = job })
      if (finalJob.status === 'ready') {
        toast.success(`${options.itemLabel} ready!`)
        savedJobs.value = [finalJob, ...savedJobs.value]
        options.onSuccess?.(finalJob)
      } else {
        toast.error(finalJob.error_message || finalJob.error || `${options.itemLabel} generation failed.`)
      }
    } catch (err) {
      log.error({ err }, `${options.itemLabel} generation failed`)
      toast.error(`${options.itemLabel} generation failed.`)
    } finally {
      isGenerating.value = false
      currentJob.value = null
    }
  }

  return {
    savedJobs,
    currentJob,
    isGenerating,
    viewingJob,
    loadSavedJobs,
    handleGeneration,
    openViewer: (job: AnyJob) => { viewingJob.value = job },
    closeViewer: () => { viewingJob.value = null },
  }
}
