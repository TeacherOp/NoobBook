<script setup lang="ts">
/**
 * GenericProgressIndicator
 * Reusable progress indicator for studio generation in progress.
 */
import { PhSpinnerGap } from '@phosphor-icons/vue'
import type { Component } from 'vue'

const props = defineProps<{
  title: string
  subtitle?: string
  icon?: Component
  colorClass?: string
  bgClass?: string
  borderClass?: string
}>()
</script>

<template>
  <div
    class="p-2 rounded-md border overflow-hidden"
    :class="[props.bgClass || 'bg-primary/5', props.borderClass || 'border-primary/20']"
  >
    <div class="flex items-center gap-2">
      <PhSpinnerGap
        :size="14"
        class="animate-spin flex-shrink-0"
        :class="props.colorClass || 'text-primary'"
      />
      <div class="flex-1 min-w-0 overflow-hidden">
        <p class="text-xs font-medium truncate" :class="props.colorClass || 'text-primary'">
          {{ props.title }}
        </p>
        <p v-if="props.subtitle" class="text-[10px] text-muted-foreground truncate">
          {{ props.subtitle }}
        </p>
      </div>
      <component v-if="props.icon" :is="props.icon" :size="12" :class="props.colorClass || 'text-primary'" class="flex-shrink-0" />
    </div>
  </div>
</template>
