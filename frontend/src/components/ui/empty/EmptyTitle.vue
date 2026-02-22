<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="empty-title"
    :class="cn('text-lg font-medium tracking-tight', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
