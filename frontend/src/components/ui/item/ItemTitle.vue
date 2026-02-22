<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="item-title"
    :class="cn('flex w-fit items-center gap-2 text-sm font-medium leading-snug', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
