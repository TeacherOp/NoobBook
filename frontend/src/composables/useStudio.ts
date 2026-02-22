/**
 * Studio Composable
 *
 * Educational Note: Vue equivalent of React's StudioContext.
 * Uses provide/inject to share state across the Studio panel subtree.
 * Only contains data needed by multiple sections — each section owns its own job state.
 */

import { ref, computed, type InjectionKey, type ComputedRef, type Ref, provide, inject, type Component, isRef } from 'vue'
import type { StudioSignal, StudioItemId } from '@/lib/types/studio'
import { generationOptions } from '@/components/studio/types'
import { createLogger } from '@/lib/logger'

const log = createLogger('studio-context')

// ==================== Types ====================

export interface StudioContext {
  // Core shared state
  projectId: string
  // signals exposed as plain array (snapshot at provider creation time)
  // Use validSourceIds computed for reactive filtering
  signals: StudioSignal[]

  // Memoized Set for O(1) source filtering
  validSourceIds: ComputedRef<Set<string>>

  // Signal picker state (shared because it's triggered from StudioToolsList)
  pickerOpen: Ref<boolean>
  selectedItem: Ref<StudioItemId | null>
  selectedSignals: Ref<StudioSignal[]>

  // Generation trigger — called by signal picker after selection
  triggerGeneration: (optionId: StudioItemId, signal: StudioSignal) => Promise<void>

  // Register generation handler from sections
  registerGenerationHandler: (itemId: StudioItemId, handler: (signal: StudioSignal) => Promise<void>) => void

  // Handle generate request from tools list
  handleGenerate: (optionId: StudioItemId, itemSignals: StudioSignal[]) => void

  // Utility functions
  getItemTitle: (itemId: StudioItemId) => string
  getItemIcon: (itemId: StudioItemId) => Component | undefined
}

// ==================== Injection Key ====================

const STUDIO_KEY: InjectionKey<StudioContext> = Symbol('studio')

// ==================== Provider ====================

/**
 * Creates studio state and provides it to the component tree.
 * Call this in StudioPanel.vue's setup.
 */
export function useStudioProvider(
  projectId: string,
  getSignals: () => StudioSignal[]
): StudioContext {
  // Signal picker state
  const pickerOpen = ref(false)
  const selectedItem = ref<StudioItemId | null>(null)
  const selectedSignals = ref<StudioSignal[]>([])

  // Registry of generation handlers from sections
  const generationHandlers = new Map<StudioItemId, (signal: StudioSignal) => Promise<void>>()

  // Computed Set of valid source IDs for O(1) filtering
  const validSourceIds = computed(() => {
    const ids = new Set<string>()
    getSignals().forEach(signal => {
      const sources = signal.sources || []
      sources.forEach(source => {
        if (source?.source_id) ids.add(source.source_id)
      })
    })
    return ids
  })

  // Register a generation handler from a section
  function registerGenerationHandler(
    itemId: StudioItemId,
    handler: (signal: StudioSignal) => Promise<void>
  ) {
    generationHandlers.set(itemId, handler)
  }

  // Get display name for a studio item
  function getItemTitle(itemId: StudioItemId): string {
    const option = generationOptions.find((opt) => opt.id === itemId)
    return option?.title || itemId
  }

  // Get icon for a studio item
  function getItemIcon(itemId: StudioItemId): Component | undefined {
    const option = generationOptions.find((opt) => opt.id === itemId)
    return option?.icon
  }

  // Trigger the actual generation workflow
  async function triggerGeneration(optionId: StudioItemId, signal: StudioSignal) {
    pickerOpen.value = false

    const handler = generationHandlers.get(optionId)
    if (handler) {
      try {
        await handler(signal)
      } catch (error) {
        log.error({ err: error }, 'generation handler threw error')
      }
    } else {
      log.warn(`no generation handler registered for: ${optionId}`)
    }
  }

  // Handle generation request from tools list
  function handleGenerate(optionId: StudioItemId, itemSignals: StudioSignal[]) {
    if (itemSignals.length === 0) return

    if (itemSignals.length === 1) {
      triggerGeneration(optionId, itemSignals[0])
    } else {
      selectedItem.value = optionId
      selectedSignals.value = itemSignals
      pickerOpen.value = true
    }
  }

  // Expose plain signals array via getter for template access
  const signals = getSignals()

  const studio: StudioContext = {
    projectId,
    signals,
    validSourceIds,
    pickerOpen,
    selectedItem,
    selectedSignals,
    triggerGeneration,
    registerGenerationHandler,
    handleGenerate,
    getItemTitle,
    getItemIcon,
  }

  provide(STUDIO_KEY, studio)
  return studio
}

// ==================== Consumer Hooks ====================

/**
 * Access studio state from any descendant component.
 */
export function useStudioContext(): StudioContext {
  const studio = inject(STUDIO_KEY)
  if (!studio) {
    throw new Error('useStudioContext() must be used within a component where useStudioProvider() was called')
  }
  return studio
}

/**
 * Filter jobs by valid source IDs (from studio signals).
 * Accepts a Ref<any[]> and returns a ComputedRef<any[]>.
 * If validSourceIds is empty (no signals yet), show all jobs.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useFilteredJobs(jobs: Ref<any[]>): ComputedRef<any[]> {
  const { validSourceIds } = useStudioContext()
  return computed(() => {
    // When no signals yet, show all saved jobs
    if (validSourceIds.value.size === 0) return jobs.value
    return jobs.value.filter((job: { source_id?: string }) =>
      job.source_id && validSourceIds.value.has(job.source_id)
    )
  })
}
