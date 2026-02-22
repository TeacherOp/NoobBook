<script setup lang="ts">
import { computed } from 'vue'
import { PhFolderOpen } from '@phosphor-icons/vue'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { type Source } from '@/lib/api/sources'
import SourceItem from './SourceItem.vue'

const props = defineProps<{
  sources: Source[]
  loading: boolean
  searchQuery: string
}>()

const emit = defineEmits<{
  download: [sourceId: string]
  delete: [sourceId: string, sourceName: string]
  rename: [sourceId: string, currentName: string]
  toggleActive: [sourceId: string, active: boolean]
  cancelProcessing: [sourceId: string]
  retryProcessing: [sourceId: string]
  viewProcessed: [sourceId: string]
}>()

const filteredSources = computed(() =>
  props.sources.filter(s =>
    s.name.toLowerCase().includes(props.searchQuery.toLowerCase())
  )
)
</script>

<template>
  <ScrollArea class="flex-1">
    <div class="p-4">
      <!-- Loading skeletons -->
      <div v-if="loading" class="space-y-2">
        <div v-for="i in 4" :key="i" class="flex items-center gap-2 p-2 rounded-lg">
          <Skeleton class="h-5 w-5 rounded" />
          <div class="flex-1 space-y-1">
            <Skeleton class="h-3.5 w-3/4" />
            <Skeleton class="h-2.5 w-1/4" />
          </div>
          <Skeleton class="h-4 w-4 rounded" />
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="filteredSources.length === 0" class="text-center py-8 text-muted-foreground">
        <PhFolderOpen :size="48" class="mx-auto mb-3 opacity-50" />
        <p class="text-sm">
          {{ searchQuery ? 'No sources match your search' : 'No sources yet' }}
        </p>
        <p class="text-xs mt-1">
          {{ searchQuery ? 'Try a different search term' : 'Add documents, images, or audio to get started' }}
        </p>
      </div>

      <!-- Source list -->
      <div v-else class="space-y-2">
        <SourceItem
          v-for="source in filteredSources"
          :key="source.id"
          :source="source"
          @download="emit('download', $event)"
          @delete="(id, name) => emit('delete', id, name)"
          @rename="(id, name) => emit('rename', id, name)"
          @toggle-active="(id, active) => emit('toggleActive', id, active)"
          @cancel-processing="emit('cancelProcessing', $event)"
          @retry-processing="emit('retryProcessing', $event)"
          @view-processed="emit('viewProcessed', $event)"
        />
      </div>
    </div>
  </ScrollArea>
</template>
