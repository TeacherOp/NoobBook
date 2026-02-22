<script setup lang="ts">
import { ScrollArea } from '@/components/ui/scroll-area'
import { useStudioContext } from '@/composables/useStudio'
import { generationOptions, categoryMeta, getSignalsForItem, type GenerationCategory } from './types'
import StudioToolItem from './StudioToolItem.vue'

const { signals, handleGenerate } = useStudioContext()

function categoryHasActiveItems(category: GenerationCategory) {
  return generationOptions
    .filter(o => o.category === category)
    .some(o => getSignalsForItem(signals.value, o.id).length > 0)
}
</script>

<template>
  <ScrollArea class="flex-1">
    <div class="p-3 space-y-3">
      <div v-for="(meta, category) in categoryMeta" :key="category">
        <div class="flex items-center gap-1.5 mb-1.5">
          <component
            :is="meta.icon"
            :size="16"
            :class="categoryHasActiveItems(category as GenerationCategory) ? 'text-primary' : 'text-muted-foreground'"
          />
          <h3
            class="text-[10px] font-semibold uppercase tracking-wider"
            :class="categoryHasActiveItems(category as GenerationCategory) ? 'text-primary' : 'text-muted-foreground'"
          >
            {{ meta.label }}
          </h3>
        </div>
        <div class="grid grid-cols-2 gap-1.5">
          <StudioToolItem
            v-for="option in generationOptions.filter(o => o.category === category)"
            :key="option.id"
            :option="option"
            :signals="getSignalsForItem(signals.value, option.id)"
            @click="(id, sigs) => handleGenerate(id, sigs)"
          />
        </div>
      </div>
    </div>
  </ScrollArea>
</template>
