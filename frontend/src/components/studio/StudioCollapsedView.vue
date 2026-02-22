<script setup lang="ts">
import { PhMagicWand, PhCaretLeft } from '@phosphor-icons/vue'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import { useStudioContext } from '@/composables/useStudio'
import { generationOptions, getSignalsForItem } from './types'

defineProps<{ onExpand: () => void }>()

const { signals, handleGenerate } = useStudioContext()
</script>

<template>
  <TooltipProvider :delay-duration="100">
    <div class="h-full flex flex-col items-center py-3 bg-card">
      <Tooltip>
        <TooltipTrigger as-child>
          <button class="p-2 rounded-lg hover:bg-muted transition-colors mb-2" @click="onExpand()">
            <PhMagicWand :size="20" class="text-primary" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="left"><p>Studio</p></TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger as-child>
          <button class="p-1.5 rounded-lg hover:bg-muted transition-colors mb-3" @click="onExpand()">
            <PhCaretLeft :size="14" class="text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="left"><p>Expand panel</p></TooltipContent>
      </Tooltip>

      <ScrollArea class="flex-1 w-full">
        <div class="flex flex-col items-center gap-1 px-1">
          <Tooltip v-for="option in generationOptions" :key="option.id">
            <TooltipTrigger as-child>
              <button
                class="p-2 rounded-lg transition-colors w-full flex justify-center relative"
                :class="getSignalsForItem(signals.value, option.id).length > 0
                  ? 'hover:bg-muted'
                  : 'opacity-30 cursor-default'"
                :disabled="getSignalsForItem(signals.value, option.id).length === 0"
                @click="getSignalsForItem(signals.value, option.id).length > 0 && handleGenerate(option.id, getSignalsForItem(signals.value, option.id))"
              >
                <component
                  :is="option.icon"
                  :size="18"
                  :class="getSignalsForItem(signals.value, option.id).length > 0 ? 'text-primary' : 'text-muted-foreground'"
                />
                <span
                  v-if="getSignalsForItem(signals.value, option.id).length > 0"
                  class="absolute top-1 right-1 w-1.5 h-1.5 bg-primary rounded-full"
                />
              </button>
            </TooltipTrigger>
            <TooltipContent side="left"><p>{{ option.title }}</p></TooltipContent>
          </Tooltip>
        </div>
      </ScrollArea>
    </div>
  </TooltipProvider>
</template>
