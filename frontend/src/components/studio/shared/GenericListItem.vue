<script setup lang="ts">
/**
 * GenericListItem
 * Reusable list item for studio generated content.
 * Used by Blog, Quiz, Presentation, Video, etc.
 */
import { PhDownloadSimple } from '@phosphor-icons/vue'
import type { Component } from 'vue'

const props = defineProps<{
  title: string
  subtitle?: string
  icon: Component
  iconColorClass?: string
  iconBgClass?: string
  clickable?: boolean
}>()

const emit = defineEmits<{
  open: []
  download: []
}>()
</script>

<template>
  <div
    class="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors"
    :class="props.clickable !== false ? 'cursor-pointer' : ''"
    @click="props.clickable !== false && emit('open')"
  >
    <div
      class="p-1.5 rounded-md flex-shrink-0"
      :class="props.iconBgClass || 'bg-primary/10'"
    >
      <component
        :is="props.icon"
        :size="16"
        :class="props.iconColorClass || 'text-primary'"
      />
    </div>
    <div class="flex-1 min-w-0 overflow-hidden">
      <p class="text-xs font-medium truncate">{{ props.title }}</p>
      <p v-if="props.subtitle" class="text-[11px] text-muted-foreground truncate">{{ props.subtitle }}</p>
    </div>
    <button
      class="p-1 hover:bg-muted rounded flex-shrink-0"
      @click.stop="emit('download')"
    >
      <PhDownloadSimple :size="14" class="text-muted-foreground" />
    </button>
  </div>
</template>
