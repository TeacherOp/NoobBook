<script setup lang="ts">
import { onMounted } from 'vue'
import { useStudioContext, useFilteredJobs } from '@/composables/useStudio'
import { useStudioGeneration } from '@/composables/useStudioGeneration'
import { infographicsAPI } from '@/lib/api/studio'
import type { StudioSignal } from '@/lib/types/studio'
import GenericListItem from '../shared/GenericListItem.vue'
import GenericProgressIndicator from '../shared/GenericProgressIndicator.vue'
import { PhChartPieSlice } from '@phosphor-icons/vue'

const { projectId, registerGenerationHandler } = useStudioContext()

const { savedJobs, currentJob, isGenerating, loadSavedJobs, handleGeneration } =
  useStudioGeneration({
    itemLabel: 'Infographic',
    loadJobs: async () => {
      const res = await infographicsAPI.listJobs(projectId)
      return res.success && res.jobs ? res.jobs.filter((j: any) => j.status === 'ready') : []
    },
    startGeneration: async (signal: StudioSignal) => {
      const sourceId = signal.sources[0]?.source_id
      if (!sourceId) return { success: false as const, error: 'No source' }
      return infographicsAPI.startGeneration(projectId, sourceId, signal.direction)
    },
    pollJobStatus: (jobId: string, onProgress: any) => infographicsAPI.pollJobStatus(projectId, jobId, onProgress),
  })

const filteredJobs = useFilteredJobs(savedJobs)

onMounted(loadSavedJobs)
registerGenerationHandler('infographics', handleGeneration)
</script>

<template>
  <template v-if="filteredJobs.length > 0 || isGenerating">
    <GenericProgressIndicator
      v-if="isGenerating"
      :title="currentJob?.source_name || 'Generating Infographic...'"
      :subtitle="(currentJob as any)?.status_message"
      :icon="PhChartPieSlice"
    />
    <GenericListItem
      v-for="job in filteredJobs"
      :key="job.id"
      :title="(job as any).title || (job as any).source_name || 'Infographic'"
      :icon="PhChartPieSlice"
      icon-bg-class="bg-violet-500/10"
      icon-color-class="text-violet-600"
      @open="() => {}"
      @download="() => {}"
    />
  </template>
</template>
