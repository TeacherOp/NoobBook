<script setup lang="ts">
import { onMounted } from 'vue'
import { useStudioContext, useFilteredJobs } from '@/composables/useStudio'
import { useStudioGeneration } from '@/composables/useStudioGeneration'
import { presentationsAPI } from '@/lib/api/studio'
import type { StudioSignal } from '@/lib/types/studio'
import GenericListItem from '../shared/GenericListItem.vue'
import GenericProgressIndicator from '../shared/GenericProgressIndicator.vue'
import { PhPresentationChart } from '@phosphor-icons/vue'

const { projectId, registerGenerationHandler } = useStudioContext()

const { savedJobs, currentJob, isGenerating, loadSavedJobs, handleGeneration } =
  useStudioGeneration({
    itemLabel: 'Presentation',
    loadJobs: async () => {
      const res = await presentationsAPI.listJobs(projectId)
      return res.success && res.jobs ? res.jobs.filter((j: any) => j.status === 'ready') : []
    },
    startGeneration: async (signal: StudioSignal) => {
      const sourceId = signal.sources[0]?.source_id
      if (!sourceId) return { success: false as const, error: 'No source' }
      return presentationsAPI.startGeneration(projectId, sourceId, signal.direction)
    },
    pollJobStatus: (jobId: string, onProgress: any) => presentationsAPI.pollJobStatus(projectId, jobId, onProgress),
  })

const filteredJobs = useFilteredJobs(savedJobs)

onMounted(loadSavedJobs)
registerGenerationHandler('presentation', handleGeneration)
</script>

<template>
  <template v-if="filteredJobs.length > 0 || isGenerating">
    <GenericProgressIndicator
      v-if="isGenerating"
      :title="currentJob?.source_name || 'Generating Presentation...'"
      :subtitle="(currentJob as any)?.status_message"
      :icon="PhPresentationChart"
    />
    <GenericListItem
      v-for="job in filteredJobs"
      :key="job.id"
      :title="(job as any).title || (job as any).source_name || 'Presentation'"
      :icon="PhPresentationChart"
      icon-bg-class="bg-blue-500/10"
      icon-color-class="text-blue-600"
      @open="() => {}"
      @download="() => {}"
    />
  </template>
</template>
