<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    :class="cn(
      'bg-muted shadow-xs flex items-center gap-2 rounded-md border px-4 text-sm font-medium [&_svg:not([class*=\'size-\'])]:size-4 [&_svg]:pointer-events-none',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
