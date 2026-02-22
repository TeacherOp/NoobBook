<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="item-actions"
    :class="cn('flex items-center gap-2', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
