<script setup lang="ts">
/**
 * StudioPanel Component
 * Educational Note: Layout-only orchestrator. Provides StudioProvider context
 * and renders collapsed/expanded views.
 *
 * The Vue equivalent of React's Context Provider pattern uses provide/inject
 * via the useStudioProvider() composable. StudioPanel calls useStudioProvider()
 * once, which provide()s the studio context to all child components.
 * Children call useStudioContext() to inject it.
 */
import { useStudioProvider } from '@/composables/useStudio'
import { ScrollArea } from '@/components/ui/scroll-area'
import StudioHeader from './StudioHeader.vue'
import StudioToolsList from './StudioToolsList.vue'
import StudioCollapsedView from './StudioCollapsedView.vue'
import StudioSignalPicker from './StudioSignalPicker.vue'
import StudioSections from './sections/StudioSections.vue'
import type { StudioSignal } from '@/lib/types/studio'

const props = defineProps<{
  projectId: string
  signals: StudioSignal[]
  isCollapsed?: boolean
  onExpand?: () => void
}>()

// Provide studio context to the entire panel subtree
useStudioProvider(props.projectId, () => props.signals)
</script>

<template>
  <!-- Collapsed icon strip -->
  <StudioCollapsedView
    v-if="props.isCollapsed"
    :on-expand="props.onExpand || (() => {})"
  />

  <!-- Expanded view -->
  <div v-else class="flex flex-col h-full">
    <StudioHeader />

    <!-- Top half: generation tool buttons -->
    <div class="flex-1 min-h-0 border-b flex flex-col">
      <StudioToolsList />
    </div>

    <!-- Bottom half: generated outputs -->
    <div class="flex-1 min-h-0 flex flex-col">
      <div class="px-3 py-2 border-b">
        <h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Generated Content
        </h3>
      </div>
      <ScrollArea class="flex-1">
        <div class="p-3 space-y-2">
          <StudioSections />
        </div>
      </ScrollArea>
    </div>

    <!-- Signal picker dialog (renders in portal, always present) -->
    <StudioSignalPicker />
  </div>
</template>
