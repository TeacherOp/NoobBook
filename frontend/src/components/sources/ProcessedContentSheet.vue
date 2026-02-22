<script setup lang="ts">
import { computed } from 'vue'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { ScrollArea } from '@/components/ui/scroll-area'

const props = defineProps<{
  open: boolean
  sourceName: string
  content: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

/**
 * Formats content by splitting on page markers and styling them.
 * Page markers look like: === PDF PAGE 1 of 5 ===
 */
const formattedParts = computed(() => {
  const pageMarkerRegex = /(===\s*\w+\s*PAGE\s*\d+\s*of\s*\d+\s*===)/gi
  const parts = props.content.split(pageMarkerRegex)
  return parts
    .map((part, index) => {
      const isMarker = /===\s*\w+\s*PAGE\s*\d+\s*of\s*\d+\s*===/i.test(part)
      if (isMarker) return { type: 'marker' as const, text: part, index }
      const trimmed = part.replace(/^\n+/, '')
      if (!trimmed) return null
      return { type: 'content' as const, text: trimmed, index }
    })
    .filter(Boolean)
})
</script>

<template>
  <Sheet :open="props.open" @update:open="emit('update:open', $event)">
    <SheetContent
      side="left"
      class="w-[95vw] sm:w-[800px] lg:w-[900px] max-w-[1000px] flex flex-col pr-0"
    >
      <SheetHeader class="pb-4 border-b pr-6">
        <SheetTitle class="text-lg font-semibold pr-8" :title="props.sourceName">
          {{ props.sourceName }}
        </SheetTitle>
      </SheetHeader>

      <ScrollArea class="flex-1 mt-4">
        <div class="pr-6 pb-8">
          <div class="text-[15px] text-stone-700 leading-7 whitespace-pre-wrap break-words tracking-normal">
            <template v-for="part in formattedParts" :key="part!.index">
              <div
                v-if="part!.type === 'marker'"
                class="mb-2 py-1.5 px-3 bg-[#f5f5f4] rounded-md text-xs font-medium text-stone-500 text-center border border-stone-200"
              >
                {{ part!.text }}
              </div>
              <span v-else>{{ part!.text }}</span>
            </template>
          </div>
        </div>
      </ScrollArea>
    </SheetContent>
  </Sheet>
</template>
