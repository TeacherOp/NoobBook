<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="empty-header"
    :class="cn('flex max-w-sm flex-col items-center gap-2 text-center', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
