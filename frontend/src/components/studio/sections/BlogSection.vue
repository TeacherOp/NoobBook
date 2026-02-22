<script setup lang="ts">
import { onMounted } from 'vue'
import { useStudioContext, useFilteredJobs } from '@/composables/useStudio'
import { useStudioGeneration } from '@/composables/useStudioGeneration'
import { blogsAPI } from '@/lib/api/studio'
import type { StudioSignal } from '@/lib/types/studio'
import GenericListItem from '../shared/GenericListItem.vue'
import GenericProgressIndicator from '../shared/GenericProgressIndicator.vue'
import { PhArticle } from '@phosphor-icons/vue'

const { projectId, registerGenerationHandler } = useStudioContext()

const { savedJobs, currentJob, isGenerating, loadSavedJobs, handleGeneration } =
  useStudioGeneration({
    itemLabel: 'Blog Post',
    loadJobs: async () => {
      const res = await blogsAPI.listJobs(projectId)
      return res.success && res.jobs ? res.jobs.filter((j: any) => j.status === 'ready') : []
    },
    startGeneration: async (signal: StudioSignal) => {
      const sourceId = signal.sources[0]?.source_id
      if (!sourceId) return { success: false as const, error: 'No source' }
      return blogsAPI.startGeneration(projectId, sourceId, signal.direction, '', 'how_to_guide')
    },
    pollJobStatus: (jobId: string, onProgress: any) => blogsAPI.pollJobStatus(projectId, jobId, onProgress),
  })

const filteredJobs = useFilteredJobs(savedJobs)

onMounted(loadSavedJobs)
registerGenerationHandler('blog', handleGeneration)
</script>

<template>
  <template v-if="filteredJobs.length > 0 || isGenerating">
    <GenericProgressIndicator
      v-if="isGenerating"
      :title="currentJob?.source_name || 'Generating Blog Post...'"
      :subtitle="(currentJob as any)?.status_message"
      :icon="PhArticle"
    />
    <GenericListItem
      v-for="job in filteredJobs"
      :key="job.id"
      :title="(job as any).title || (job as any).source_name || 'Blog Post'"
      :icon="PhArticle"
      icon-bg-class="bg-indigo-500/10"
      icon-color-class="text-indigo-600"
      @open="() => {}"
      @download="() => {}"
    />
  </template>
</template>
