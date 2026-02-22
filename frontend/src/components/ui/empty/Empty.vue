<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="empty"
    :class="cn(
      'flex min-w-0 flex-1 flex-col items-center justify-center gap-6 text-balance rounded-lg border-dashed p-6 text-center md:p-12',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
