<script setup lang="ts">
/**
 * SourcesPanel Component
 * Educational Note: Main orchestrator for sources. Manages state and API calls,
 * delegates rendering to child components.
 *
 * Key Vue patterns:
 * - `watch` replaces useEffect with dependency array
 * - `onMounted` replaces useEffect([])
 * - Polling via setInterval managed in watch + onUnmounted
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  PhBooks, PhCaretRight, PhPlus,
  PhFilePdf, PhFileDoc, PhFilePpt, PhFileCsv, PhFileHtml,
  PhFilePng, PhFile, PhFileText, PhMarkdownLogo, PhTable,
  PhLink, PhImage, PhMusicNote, PhYoutubeLogo,
} from '@phosphor-icons/vue'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { sourcesAPI, MAX_SOURCES, isSourceViewable, type Source } from '@/lib/api/sources'
import { chatsAPI } from '@/lib/api/chats'
import { createLogger } from '@/lib/logger'
import SourcesHeader from './SourcesHeader.vue'
import SourcesList from './SourcesList.vue'
import SourcesFooter from './SourcesFooter.vue'
import AddSourcesSheet from './AddSourcesSheet.vue'
import ProcessedContentSheet from './ProcessedContentSheet.vue'

const log = createLogger('sources-panel')

const props = withDefaults(defineProps<{
  projectId: string
  isCollapsed?: boolean
  activeChatId?: string | null
  selectedSourceIds?: string[]
}>(), {
  isCollapsed: false,
  activeChatId: null,
  selectedSourceIds: () => [],
})

const emit = defineEmits<{
  expand: []
  sourcesChange: []
  selectedSourcesChange: [ids: string[]]
}>()

// ── State ─────────────────────────────────────────────────────────────────────
const sources = ref<Source[]>([])
const loading = ref(true)
const sheetOpen = ref(false)
const searchQuery = ref('')
const uploading = ref(false)

const renameDialogOpen = ref(false)
const renameSourceId = ref<string | null>(null)
const renameValue = ref('')

const viewerOpen = ref(false)
const viewerContent = ref('')
const viewerSourceName = ref('')

// Prevent stale poll from reverting optimistic toggles
const recentToggles = new Set<string>()
let prevSources: Source[] = []
let pollTimer: ReturnType<typeof setInterval> | null = null

// ── Icon helper ───────────────────────────────────────────────────────────────
function getSourceIcon(source: Source) {
  const name = source.name || ''
  const lastDot = name.lastIndexOf('.')
  const nameExt = lastDot > 0 ? name.substring(lastDot).toLowerCase() : ''
  const embExt = ((source.embedding_info as Record<string, string>)?.file_extension || '').toLowerCase()
  const ext = nameExt || embExt
  switch (ext) {
    case '.pdf':  return PhFilePdf
    case '.docx': return PhFileDoc
    case '.pptx': return PhFilePpt
    case '.txt':  return PhFileText
    case '.csv':  return PhFileCsv
    case '.md':   return PhMarkdownLogo
    case '.html': return PhFileHtml
    case '.json': case '.xml': return PhFileText
    case '.mp3': case '.wav': case '.m4a': case '.aac': case '.flac': return PhMusicNote
    case '.jpg': case '.jpeg': case '.png': return PhFilePng
    case '.gif': case '.webp': return PhImage
    case '.database': return PhTable
  }
  switch (source.type) {
    case 'YOUTUBE': return PhYoutubeLogo
    case 'LINK': case 'RESEARCH': return PhLink
    case 'TEXT':  return PhFileText
    case 'AUDIO': return PhMusicNote
    case 'IMAGE': return PhImage
    case 'DATA': case 'DATABASE': return PhTable
    default: return PhFile
  }
}

// ── Computed ──────────────────────────────────────────────────────────────────
const totalSize = computed(() => sources.value.reduce((s, src) => s + src.file_size, 0))
const sourcesCount = computed(() => sources.value.length)
const isAtLimit = computed(() => sourcesCount.value >= MAX_SOURCES)

// ── Load / refresh ────────────────────────────────────────────────────────────
async function loadSources() {
  try {
    loading.value = true
    const data = await sourcesAPI.listSources(props.projectId)
    const ids = props.selectedSourceIds
    sources.value = data.map(s => ({ ...s, active: ids.includes(s.id) }))
  } catch (err) {
    log.error({ err }, 'failed to load sources')
    toast.error('Failed to load sources')
  } finally {
    loading.value = false
  }
}

async function refreshSources() {
  try {
    const data = await sourcesAPI.listSources(props.projectId)
    const ids = props.selectedSourceIds
    sources.value = data.map(source => {
      if (recentToggles.has(source.id)) {
        const local = sources.value.find(s => s.id === source.id)
        if (local) return { ...source, active: local.active }
      }
      return { ...source, active: ids.includes(source.id) }
    })
  } catch (err) {
    log.error({ err }, 'silent refresh failed')
  }
}

// ── Watchers ──────────────────────────────────────────────────────────────────
// Detect newly-ready sources → notify parent
watch(sources, (current) => {
  const hasNewReady = current.some(s => {
    const prev = prevSources.find(p => p.id === s.id)
    return s.status === 'ready' && (!prev || prev.status !== 'ready')
  })
  const oldLength = prevSources.length
  prevSources = [...current]
  if (hasNewReady && oldLength > 0) emit('sourcesChange')
}, { deep: false })

// Sync active flags when selectedSourceIds prop changes
watch(() => props.selectedSourceIds, (ids) => {
  sources.value = sources.value.map(s => ({ ...s, active: ids.includes(s.id) }))
})

// Start/stop polling based on active processing
watch(sources, (current) => {
  const hasActive = current.some(s => s.status === 'processing' || s.status === 'embedding')
  if (hasActive && !pollTimer) {
    pollTimer = setInterval(refreshSources, 3000)
  } else if (!hasActive && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}, { deep: false })

onMounted(loadSources)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

// ── Action handlers ───────────────────────────────────────────────────────────
async function handleFileUpload(files: File[]) {
  if (sources.value.length + files.length > MAX_SOURCES) {
    toast.error(`Cannot upload. Maximum ${MAX_SOURCES} sources allowed.`)
    return
  }
  uploading.value = true
  try {
    for (const file of files) await sourcesAPI.uploadSource(props.projectId, file)
    toast.success(`Uploaded ${files.length} file(s) successfully`)
    await loadSources()
    sheetOpen.value = false
  } catch (err: any) {
    toast.error(err?.response?.data?.error || err?.message || 'Upload failed')
  } finally {
    uploading.value = false
  }
}

async function handleAddUrl(url: string) {
  if (isAtLimit.value) { toast.error(`Maximum ${MAX_SOURCES} sources allowed.`); return }
  try {
    await sourcesAPI.addUrlSource(props.projectId, url)
    toast.success('URL source added successfully')
    await loadSources()
    sheetOpen.value = false
  } catch (err: any) {
    toast.error(err?.response?.data?.error || 'Failed to add URL')
  }
}

async function handleAddText(content: string, name: string) {
  if (isAtLimit.value) { toast.error(`Maximum ${MAX_SOURCES} sources allowed.`); return }
  try {
    await sourcesAPI.addTextSource(props.projectId, content, name)
    toast.success('Text source added successfully')
    await loadSources()
    sheetOpen.value = false
  } catch (err: any) {
    toast.error(err?.response?.data?.error || 'Failed to add text')
  }
}

async function handleAddResearch(topic: string, description: string, links: string[]) {
  if (isAtLimit.value) { toast.error(`Maximum ${MAX_SOURCES} sources allowed.`); return }
  try {
    await sourcesAPI.addResearchSource(props.projectId, topic, description, links)
    toast.success('Deep research started — this may take a few minutes')
    await loadSources()
    sheetOpen.value = false
  } catch (err: any) {
    toast.error(err?.response?.data?.error || 'Failed to start research')
  }
}

async function handleAddDatabase(connectionId: string, name?: string, description?: string) {
  if (isAtLimit.value) { toast.error(`Maximum ${MAX_SOURCES} sources allowed.`); return }
  try {
    await sourcesAPI.addDatabaseSource(props.projectId, connectionId, name, description)
    toast.success('Database source added successfully')
    await loadSources()
    sheetOpen.value = false
  } catch (err: any) {
    toast.error(err?.response?.data?.error || 'Failed to add database')
  }
}

async function handleDeleteSource(sourceId: string, sourceName: string) {
  try {
    await sourcesAPI.deleteSource(props.projectId, sourceId)
    toast.success(`Deleted "${sourceName}"`)
    await loadSources()
    emit('sourcesChange')
  } catch {
    toast.error('Failed to delete source')
  }
}

function handleDownloadSource(sourceId: string) {
  const path = sourcesAPI.getDownloadUrl(props.projectId, sourceId)
  window.open(path, '_blank')
}

function openRename(sourceId: string, currentName: string) {
  renameSourceId.value = sourceId
  renameValue.value = currentName
  renameDialogOpen.value = true
}

async function submitRename() {
  if (!renameSourceId.value || !renameValue.value.trim()) return
  try {
    await sourcesAPI.updateSource(props.projectId, renameSourceId.value, { name: renameValue.value.trim() })
    toast.success('Source renamed')
    renameDialogOpen.value = false
    await loadSources()
  } catch {
    toast.error('Failed to rename source')
  }
}

async function handleToggleActive(sourceId: string, active: boolean) {
  if (!props.activeChatId) {
    toast.error('Create or select a chat first to toggle sources')
    return
  }
  const newIds = active
    ? [...props.selectedSourceIds, sourceId]
    : props.selectedSourceIds.filter(id => id !== sourceId)

  sources.value = sources.value.map(s => s.id === sourceId ? { ...s, active } : s)
  emit('selectedSourcesChange', newIds)
  recentToggles.add(sourceId)

  try {
    await chatsAPI.updateChatSources(props.projectId, props.activeChatId, newIds)
  } catch {
    toast.error('Failed to update source selection')
    const revertedIds = active
      ? props.selectedSourceIds.filter(id => id !== sourceId)
      : [...props.selectedSourceIds, sourceId]
    emit('selectedSourcesChange', revertedIds)
    sources.value = sources.value.map(s => s.id === sourceId ? { ...s, active: !active } : s)
  } finally {
    setTimeout(() => recentToggles.delete(sourceId), 5000)
  }
}

async function handleCancelProcessing(sourceId: string) {
  try {
    await sourcesAPI.cancelProcessing(props.projectId, sourceId)
    toast.success('Processing cancelled')
    await loadSources()
  } catch {
    toast.error('Failed to cancel processing')
  }
}

async function handleRetryProcessing(sourceId: string) {
  try {
    await sourcesAPI.retryProcessing(props.projectId, sourceId)
    toast.success('Processing restarted')
    await loadSources()
  } catch {
    toast.error('Failed to retry processing')
  }
}

async function handleViewProcessed(sourceId: string) {
  try {
    const data = await sourcesAPI.getProcessedContent(props.projectId, sourceId)
    viewerContent.value = data.content
    viewerSourceName.value = data.source_name
    viewerOpen.value = true
  } catch {
    toast.error('Failed to load processed content')
  }
}
</script>

<template>
  <!-- Collapsed sidebar: icon strip -->
  <TooltipProvider v-if="props.isCollapsed" :delay-duration="100">
    <div class="h-full flex flex-col items-center py-3 bg-card">
      <Tooltip>
        <TooltipTrigger as-child>
          <button class="p-2.5 rounded-lg hover:bg-muted transition-colors mb-2" @click="emit('expand')">
            <PhBooks :size="24" class="text-primary" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right"><p>Sources</p></TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger as-child>
          <button class="p-2 rounded-lg hover:bg-muted transition-colors mb-3" @click="emit('expand')">
            <PhCaretRight :size="16" class="text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right"><p>Expand panel</p></TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger as-child>
          <button
            class="p-2.5 rounded-lg hover:bg-muted transition-colors mb-1"
            :class="isAtLimit ? 'opacity-30 cursor-default' : ''"
            :disabled="isAtLimit"
            @click="sheetOpen = true"
          >
            <PhPlus :size="20" class="text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right"><p>Add sources</p></TooltipContent>
      </Tooltip>

      <ScrollArea class="flex-1 w-full">
        <div class="flex flex-col items-center gap-1.5 px-1">
          <Tooltip v-for="source in sources" :key="source.id">
            <TooltipTrigger as-child>
              <button
                class="p-2.5 rounded-lg hover:bg-muted transition-colors w-full flex justify-center"
                @click="isSourceViewable(source) ? handleViewProcessed(source.id) : emit('expand')"
              >
                <component :is="getSourceIcon(source)" :size="22" weight="bold" class="text-muted-foreground" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p class="max-w-[200px] truncate">{{ source.name }}</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </ScrollArea>
    </div>
  </TooltipProvider>

  <!-- Expanded view -->
  <div v-else class="flex flex-col h-full">
    <SourcesHeader
      :search-query="searchQuery"
      :is-at-limit="isAtLimit"
      @update:search-query="searchQuery = $event"
      @add-click="sheetOpen = true"
    />
    <SourcesList
      :sources="sources"
      :loading="loading"
      :search-query="searchQuery"
      @download="handleDownloadSource"
      @delete="(id, name) => handleDeleteSource(id, name)"
      @rename="(id, name) => openRename(id, name)"
      @toggle-active="(id, active) => handleToggleActive(id, active)"
      @cancel-processing="handleCancelProcessing"
      @retry-processing="handleRetryProcessing"
      @view-processed="handleViewProcessed"
    />
    <SourcesFooter :sources-count="sourcesCount" :total-size="totalSize" />
  </div>

  <!-- Add Sources Sheet -->
  <AddSourcesSheet
    :open="sheetOpen"
    :project-id="props.projectId"
    :sources-count="sourcesCount"
    :uploading="uploading"
    @update:open="sheetOpen = $event"
    @upload="handleFileUpload"
    @add-url="handleAddUrl"
    @add-text="(content, name) => handleAddText(content, name)"
    @add-research="(t, d, l) => handleAddResearch(t, d, l)"
    @add-database="(id, name, desc) => handleAddDatabase(id, name, desc)"
    @import-complete="loadSources"
  />

  <!-- Rename Dialog -->
  <Dialog :open="renameDialogOpen" @update:open="renameDialogOpen = $event">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>Rename Source</DialogTitle>
        <DialogDescription>Enter a new name for this source.</DialogDescription>
      </DialogHeader>
      <div class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="rename-input">Name</Label>
          <Input
            id="rename-input"
            v-model="renameValue"
            placeholder="Source name"
            @keydown.enter="submitRename"
          />
        </div>
      </div>
      <DialogFooter>
        <Button variant="soft" @click="renameDialogOpen = false">Cancel</Button>
        <Button :disabled="!renameValue.trim()" @click="submitRename">Rename</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Processed Content Viewer -->
  <ProcessedContentSheet
    :open="viewerOpen"
    :source-name="viewerSourceName"
    :content="viewerContent"
    @update:open="viewerOpen = $event"
  />
</template>
