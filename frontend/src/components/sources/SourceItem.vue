<script setup lang="ts">
/**
 * SourceItem Component
 * Educational Note: Displays a single source with icon, name, status, and action menu.
 * - On hover: category icon → 3-dot menu, spinner → stop button, warning → retry
 * - Active checkbox only enabled for ready sources (per-chat selection)
 */
import { computed } from 'vue'
import {
  PhFileText, PhFilePdf, PhFileDoc, PhFilePpt, PhFileCsv, PhFileHtml,
  PhFilePng, PhFile, PhMusicNote, PhImage, PhTable, PhTrash,
  PhDownloadSimple, PhLink, PhYoutubeLogo, PhCircleNotch, PhWarning,
  PhDotsThreeVertical, PhPencilSimple, PhStop, PhArrowClockwise,
} from '@phosphor-icons/vue'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Checkbox } from '@/components/ui/checkbox'
import { formatFileSize, isSourceViewable, type Source } from '@/lib/api/sources'

const props = defineProps<{ source: Source }>()

const emit = defineEmits<{
  download: [sourceId: string]
  delete: [sourceId: string, sourceName: string]
  rename: [sourceId: string, currentName: string]
  toggleActive: [sourceId: string, active: boolean]
  cancelProcessing: [sourceId: string]
  retryProcessing: [sourceId: string]
  viewProcessed: [sourceId: string]
}>()

// ── Icon logic ──────────────────────────────────────────────────────────────
const sourceIcon = computed(() => {
  const name = props.source.name || ''
  const lastDot = name.lastIndexOf('.')
  const nameExt = lastDot > 0 ? name.substring(lastDot).toLowerCase() : ''
  const embExt = ((props.source.embedding_info as Record<string, string>)?.file_extension || '').toLowerCase()
  const ext = nameExt || embExt

  switch (ext) {
    case '.pdf':  return PhFilePdf
    case '.docx': return PhFileDoc
    case '.pptx': return PhFilePpt
    case '.txt':  return PhFileText
    case '.csv':  return PhFileCsv
    case '.database': return PhTable
    case '.md':   return PhFileText
    case '.html': return PhFileHtml
    case '.json': case '.xml': return PhFileText
    case '.mp3': case '.wav': case '.m4a': case '.aac': case '.flac': return PhMusicNote
    case '.jpg': case '.jpeg': return PhFilePng
    case '.png': return PhFilePng
    case '.gif': case '.webp': return PhImage
  }
  switch (props.source.type) {
    case 'YOUTUBE':   return PhYoutubeLogo
    case 'LINK': case 'RESEARCH': return PhLink
    case 'TEXT':      return PhFileText
    case 'AUDIO':     return PhMusicNote
    case 'IMAGE':     return PhImage
    case 'DATA': case 'DATABASE': return PhTable
    default:          return PhFile
  }
})

// ── Status logic ─────────────────────────────────────────────────────────────
const isProcessing      = computed(() => props.source.status === 'processing')
const isEmbedding       = computed(() => props.source.status === 'embedding')
const isActivelyWorking = computed(() => isProcessing.value || isEmbedding.value)
const isWaiting         = computed(() => props.source.status === 'uploaded')
const isError           = computed(() => props.source.status === 'error')
const canToggleActive   = computed(() => props.source.status === 'ready')
const canView           = computed(() => isSourceViewable(props.source))

const spinnerColor = computed(() =>
  isEmbedding.value ? 'text-blue-500' : 'text-primary'
)

const errorTooltip = computed(() => {
  const err = ((props.source.processing_info as Record<string, string>)?.error || '').toLowerCase()
  if (err.includes('requestblocked') || (err.includes('ip') && err.includes('cloud')))
    return 'YouTube blocks cloud server IPs. Works when self-hosted locally.'
  if (err.includes('no transcript') || err.includes('disabled'))
    return 'No transcript available for this video.'
  if (err.includes('unavailable') || err.includes('private'))
    return 'Video is unavailable (private, deleted, or region-locked).'
  if (err.includes('api key')) return 'API key is invalid or expired.'
  const raw = ((props.source.processing_info as Record<string, string>)?.error || '')
  return raw ? (raw.length <= 100 ? raw : raw.substring(0, 100) + '...') : 'Processing failed'
})

// ── Row click ────────────────────────────────────────────────────────────────
function handleRowClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest('button') || target.closest('[role="checkbox"]')) return
  if (canView.value) emit('viewProcessed', props.source.id)
}
</script>

<template>
  <div
    class="grid grid-cols-[auto_1fr_auto_auto] items-center gap-2 p-2 rounded-lg hover:bg-accent group transition-colors"
    :class="[isActivelyWorking ? 'opacity-60' : '', canView ? 'cursor-pointer' : '']"
    @click="handleRowClick"
  >
    <!-- Icon / 3-dot menu trigger -->
    <DropdownMenu>
      <DropdownMenuTrigger as-child>
        <button class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded transition-colors">
          <component :is="sourceIcon" :size="18" weight="bold" class="text-muted-foreground group-hover:hidden" />
          <PhDotsThreeVertical :size="18" weight="bold" class="text-muted-foreground hidden group-hover:block" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" @click.stop>
        <DropdownMenuItem v-if="isError || isWaiting" @click="emit('retryProcessing', source.id)">
          <PhArrowClockwise :size="14" class="mr-2" />
          {{ isWaiting ? 'Start Processing' : 'Retry Processing' }}
        </DropdownMenuItem>
        <DropdownMenuItem v-if="isActivelyWorking" @click="emit('cancelProcessing', source.id)">
          <PhStop :size="14" class="mr-2" />
          {{ isEmbedding ? 'Stop Embedding' : 'Stop Processing' }}
        </DropdownMenuItem>
        <DropdownMenuItem :disabled="isActivelyWorking" @click="emit('rename', source.id, source.name)">
          <PhPencilSimple :size="14" class="mr-2" />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem :disabled="isActivelyWorking" @click="emit('download', source.id)">
          <PhDownloadSimple :size="14" class="mr-2" />
          Download
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          class="text-destructive focus:text-destructive"
          @click="emit('delete', source.id, source.name)"
        >
          <PhTrash :size="14" class="mr-2" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>

    <!-- Source info -->
    <div class="overflow-hidden">
      <p class="text-sm truncate" :title="source.name">{{ source.name }}</p>
      <div class="flex items-center gap-2">
        <p class="text-xs text-muted-foreground">{{ formatFileSize(source.file_size) }}</p>
        <span
          v-if="source.status !== 'ready'"
          class="text-xs truncate max-w-[140px]"
          :class="isError ? 'text-destructive' : isActivelyWorking ? (isEmbedding ? 'text-blue-500' : 'text-primary') : 'text-muted-foreground'"
          :title="isError ? errorTooltip : undefined"
        >
          {{ isError ? 'Processing failed' : isActivelyWorking ? (isEmbedding ? 'Embedding...' : 'Processing...') : 'Ready to process' }}
        </span>
      </div>
    </div>

    <!-- Active checkbox -->
    <Checkbox
      :checked="source.active"
      :disabled="!canToggleActive"
      class="flex-shrink-0"
      :class="!canToggleActive ? 'opacity-30' : ''"
      :title="canToggleActive
        ? (source.active ? 'Click to exclude from chat' : 'Click to include in chat')
        : 'Source must be processed first'"
      @update:checked="(v: boolean | 'indeterminate') => emit('toggleActive', source.id, v === true)"
    />

    <!-- Status icon (non-ready states) -->
    <template v-if="source.status !== 'ready'">
      <!-- Actively working: spinner → stop on hover -->
      <button
        v-if="isActivelyWorking"
        class="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-destructive/10 transition-colors"
        :title="isEmbedding ? 'Click to stop embedding' : 'Click to stop processing'"
        @click.stop="emit('cancelProcessing', source.id)"
      >
        <PhCircleNotch :size="16" class="animate-spin group-hover:hidden" :class="spinnerColor" />
        <PhStop :size="16" weight="fill" class="text-destructive hidden group-hover:block" />
      </button>

      <!-- Waiting: retry icon -->
      <button
        v-else-if="isWaiting"
        class="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-accent transition-colors"
        title="Click to start processing"
        @click.stop="emit('retryProcessing', source.id)"
      >
        <PhArrowClockwise :size="16" weight="bold" class="text-muted-foreground group-hover:text-primary" />
      </button>

      <!-- Error: warning → retry on hover -->
      <button
        v-else-if="isError"
        class="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-accent transition-colors"
        :title="errorTooltip"
        @click.stop="emit('retryProcessing', source.id)"
      >
        <PhWarning :size="16" class="text-destructive group-hover:hidden" />
        <PhArrowClockwise :size="16" weight="bold" class="text-primary hidden group-hover:block" />
      </button>
    </template>
  </div>
</template>
