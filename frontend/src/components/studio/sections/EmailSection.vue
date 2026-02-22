<script setup lang="ts">
import { onMounted } from 'vue'
import { useStudioContext, useFilteredJobs } from '@/composables/useStudio'
import { useStudioGeneration } from '@/composables/useStudioGeneration'
import { emailsAPI } from '@/lib/api/studio'
import type { StudioSignal } from '@/lib/types/studio'
import GenericListItem from '../shared/GenericListItem.vue'
import GenericProgressIndicator from '../shared/GenericProgressIndicator.vue'
import { PhEnvelopeSimple } from '@phosphor-icons/vue'

const { projectId, registerGenerationHandler } = useStudioContext()

const { savedJobs, currentJob, isGenerating, loadSavedJobs, handleGeneration } =
  useStudioGeneration({
    itemLabel: 'Email Templates',
    loadJobs: async () => {
      const res = await emailsAPI.listJobs(projectId)
      return res.success && res.jobs ? res.jobs.filter((j: any) => j.status === 'ready') : []
    },
    startGeneration: async (signal: StudioSignal) => {
      const sourceId = signal.sources[0]?.source_id
      if (!sourceId) return { success: false as const, error: 'No source' }
      return emailsAPI.startGeneration(projectId, sourceId, signal.direction)
    },
    pollJobStatus: (jobId: string, onProgress: any) => emailsAPI.pollJobStatus(projectId, jobId, onProgress),
  })

const filteredJobs = useFilteredJobs(savedJobs)

onMounted(loadSavedJobs)
registerGenerationHandler('email_templates', handleGeneration)
</script>

<template>
  <template v-if="filteredJobs.length > 0 || isGenerating">
    <GenericProgressIndicator
      v-if="isGenerating"
      :title="currentJob?.source_name || 'Generating Email Templates...'"
      :subtitle="(currentJob as any)?.status_message"
      :icon="PhEnvelopeSimple"
    />
    <GenericListItem
      v-for="job in filteredJobs"
      :key="job.id"
      :title="(job as any).title || (job as any).source_name || 'Email Templates'"
      :icon="PhEnvelopeSimple"
      icon-bg-class="bg-teal-500/10"
      icon-color-class="text-teal-600"
      @open="() => {}"
      @download="() => {}"
    />
  </template>
</template>
