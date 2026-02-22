<script setup lang="ts">
/**
 * ProjectWorkspace Component
 * Educational Note: 3-panel resizable layout. Key Vue differences:
 * - Template refs replace React's `useRef<ImperativePanelHandle>`
 * - `ref()` replaces `useState()` for panel open/close state
 * - Events replace callback props
 */
import { ref } from 'vue'
import { PhCaretLeft, PhCaretRight, PhWarning } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable'
import ProjectHeader from './ProjectHeader.vue'
import SourcesPanel from '@/components/sources/SourcesPanel.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import StudioPanel from '@/components/studio/StudioPanel.vue'
import type { StudioSignal } from '@/lib/types/studio'

interface Project {
  id: string
  name: string
  description: string
}

const props = defineProps<{
  project: Project
  onSignOut?: () => Promise<void>
}>()

const emit = defineEmits<{
  back: []
  deleteProject: [projectId: string]
  renameProject: [newName: string]
}>()

// Resizable panel template refs
const leftPanelRef = ref<{ collapse: () => void; expand: () => void } | null>(null)
const rightPanelRef = ref<{ collapse: () => void; expand: () => void } | null>(null)

// Panel visibility state
const leftPanelOpen = ref(true)
const rightPanelOpen = ref(true)

// Version counters for cross-panel updates
const costsVersion = ref(0)
const sourcesVersion = ref(0)

function handleCostsChange() {
  costsVersion.value++
}

function handleSourcesChange() {
  sourcesVersion.value++
  costsVersion.value++
}

// Studio signals: chat → studio communication
const studioSignals = ref<StudioSignal[]>([])

function handleSignalsChange(signals: StudioSignal[]) {
  studioSignals.value = signals
}

// Per-chat source selection
const activeChatId = ref<string | null>(null)
const selectedSourceIds = ref<string[]>([])

function handleActiveChatChange(chatId: string | null, sourceIds: string[]) {
  activeChatId.value = chatId
  selectedSourceIds.value = sourceIds
}

function handleSelectedSourcesChange(newIds: string[]) {
  selectedSourceIds.value = newIds
}
</script>

<template>
  <div class="h-screen flex flex-col bg-background">
    <!-- Project Header -->
    <ProjectHeader
      :project="props.project"
      :costs-version="costsVersion"
      :on-sign-out="props.onSignOut"
      @back="emit('back')"
      @delete="emit('deleteProject', props.project.id)"
      @rename="(name: string) => emit('renameProject', name)"
    />

    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col px-3 min-h-0">
      <div class="flex-1 rounded-xl overflow-hidden bg-background min-h-0">
        <ResizablePanelGroup direction="horizontal" class="h-full">

          <!-- Left Panel - Sources -->
          <ResizablePanel
            ref="leftPanelRef"
            :default-size="20"
            :min-size="15"
            :max-size="40"
            :collapsible="true"
            :collapsed-size="4"
            class="bg-card overflow-hidden rounded-xl"
            @collapse="leftPanelOpen = false"
            @expand="leftPanelOpen = true"
          >
            <div class="h-full flex flex-col relative">
              <SourcesPanel
                :project-id="props.project.id"
                :is-collapsed="!leftPanelOpen"
                :active-chat-id="activeChatId"
                :selected-source-ids="selectedSourceIds"
                @expand="leftPanelRef?.expand()"
                @sources-change="handleSourcesChange"
                @selected-sources-change="handleSelectedSourcesChange"
              />
              <Button
                v-if="leftPanelOpen"
                variant="ghost"
                size="icon"
                class="absolute top-2 right-2 z-10 h-8 w-8 hover:bg-muted"
                @click="leftPanelRef?.collapse()"
              >
                <PhCaretLeft :size="16" />
              </Button>
            </div>
          </ResizablePanel>

          <ResizableHandle />

          <!-- Center Panel - Chat -->
          <ResizablePanel
            :default-size="55"
            :min-size="30"
            class="bg-card overflow-hidden rounded-xl min-w-0"
          >
            <div class="h-full min-h-0 min-w-0 w-full flex flex-col overflow-hidden">
              <ChatPanel
                :project-id="props.project.id"
                :project-name="props.project.name"
                :sources-version="sourcesVersion"
                :selected-source-ids="selectedSourceIds"
                @costs-change="handleCostsChange"
                @signals-change="handleSignalsChange"
                @active-chat-change="handleActiveChatChange"
              />
            </div>
          </ResizablePanel>

          <ResizableHandle />

          <!-- Right Panel - Studio -->
          <ResizablePanel
            ref="rightPanelRef"
            :default-size="25"
            :min-size="18"
            :max-size="40"
            :collapsible="true"
            :collapsed-size="4"
            class="bg-card overflow-hidden rounded-xl"
            @collapse="rightPanelOpen = false"
            @expand="rightPanelOpen = true"
          >
            <div class="h-full flex flex-col relative">
              <StudioPanel
                :project-id="props.project.id"
                :signals="studioSignals"
                :is-collapsed="!rightPanelOpen"
                @expand="rightPanelRef?.expand()"
              />
              <Button
                v-if="rightPanelOpen"
                variant="ghost"
                size="icon"
                class="absolute top-2 left-2 z-10 h-8 w-8 hover:bg-muted"
                @click="rightPanelRef?.collapse()"
              >
                <PhCaretRight :size="16" />
              </Button>
            </div>
          </ResizablePanel>

        </ResizablePanelGroup>
      </div>

      <!-- Footer Disclaimer -->
      <div class="flex items-center justify-center gap-1.5 text-xs text-muted-foreground py-1">
        <PhWarning :size="12" />
        <span>NoobBook can make mistakes. Please verify important information.</span>
      </div>
    </div>
  </div>
</template>
