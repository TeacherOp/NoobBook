<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <kbd
    data-slot="kbd-group"
    :class="cn('inline-flex items-center gap-1', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </kbd>
</template>
