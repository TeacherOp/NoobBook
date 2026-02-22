<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { GenerationOption, StudioSignal, StudioItemId } from './types'

const props = defineProps<{
  option: GenerationOption
  signals: StudioSignal[]
}>()

const emit = defineEmits<{
  click: [optionId: StudioItemId, signals: StudioSignal[]]
}>()

const isActive = computed(() => props.signals.length > 0)
</script>

<template>
  <Button
    variant="soft"
    :class="cn(
      'h-8 px-2 py-1 justify-start text-left relative text-xs',
      isActive
        ? 'hover:bg-accent border-primary/30 bg-primary/5'
        : 'opacity-50 hover:opacity-70 hover:bg-muted cursor-default'
    )"
    :disabled="!isActive"
    @click="isActive && emit('click', option.id, signals)"
  >
    <component
      :is="option.icon"
      :size="14"
      :class="cn('mr-1.5 flex-shrink-0', isActive ? 'text-primary' : 'text-muted-foreground')"
    />
    <span :class="cn('truncate', isActive ? 'text-foreground' : 'text-muted-foreground')">
      {{ option.title }}
    </span>
    <!-- Active indicator dot -->
    <span
      v-if="isActive"
      class="absolute right-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-primary rounded-full"
    />
  </Button>
</template>
