<script setup lang="ts">
/**
 * CitationBadge Component
 * Educational Note: Inline citation number that fetches and shows chunk content on hover.
 * HoverCard opens on mouse-enter, fetches content once, caches it.
 */
import { ref } from 'vue'
import { PhFileText, PhCircleNotch } from '@phosphor-icons/vue'
import {
  HoverCard, HoverCardContent, HoverCardTrigger,
} from '@/components/ui/hover-card'
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { sourcesAPI, type ChunkContent } from '@/lib/api/sources'
import { createLogger } from '@/lib/logger'

const log = createLogger('citation-badge')

const props = defineProps<{
  citationNumber: number
  chunkId: string
  pageNumber: number
  projectId: string
  sourceName?: string
}>()

const chunkContent = ref<ChunkContent | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)
const hasLoaded = ref(false)

async function handleOpenChange(open: boolean) {
  if (open && !hasLoaded.value && !loading.value) {
    loading.value = true
    loadError.value = null
    try {
      chunkContent.value = await sourcesAPI.getCitationContent(props.projectId, props.chunkId)
      hasLoaded.value = true
    } catch (err) {
      log.error({ err }, 'failed to fetch citation content')
      loadError.value = 'Failed to load citation content'
    } finally {
      loading.value = false
    }
  }
}

function cleanContent(content: string): string {
  return content
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]+/g, ' ')
    .split('\n').map(l => l.trim()).join('\n')
    .trim()
}
</script>

<template>
  <HoverCard :open-delay="200" :close-delay="100" @update:open="handleOpenChange">
    <HoverCardTrigger as-child>
      <Badge
        class="cursor-pointer text-[11px] px-2 py-0.5 h-[18px] align-super -mt-1 bg-primary text-primary-foreground hover:bg-primary/90 border-0"
      >
        {{ props.citationNumber }}
      </Badge>
    </HoverCardTrigger>
    <HoverCardContent class="w-[28rem] p-0" side="top" align="start">
      <Card class="border-0 shadow-none">
        <CardHeader class="p-3 pb-2">
          <div class="flex items-center gap-2">
            <PhFileText :size="16" class="text-primary flex-shrink-0" />
            <div class="min-w-0 flex-1">
              <CardTitle class="text-sm font-medium truncate">
                {{ chunkContent?.source_name || props.sourceName || 'Source' }}
              </CardTitle>
              <CardDescription class="text-xs">
                Page {{ props.pageNumber }}
                <template v-if="chunkContent && chunkContent.chunk_index > 1">
                  , Section {{ chunkContent.chunk_index }}
                </template>
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent class="p-3 pt-0 max-h-72 overflow-y-auto">
          <div v-if="loading" class="flex items-center gap-2 text-muted-foreground py-2">
            <PhCircleNotch :size="14" class="animate-spin" />
            <span class="text-xs">Loading...</span>
          </div>
          <p v-else-if="loadError" class="text-xs text-destructive">{{ loadError }}</p>
          <p v-else-if="chunkContent" class="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {{ cleanContent(chunkContent.content) }}
          </p>
          <p v-else class="text-xs text-muted-foreground">Loading content...</p>
        </CardContent>
      </Card>
    </HoverCardContent>
  </HoverCard>
</template>
