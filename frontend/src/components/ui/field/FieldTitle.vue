<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="field-label"
    :class="cn(
      'flex w-fit items-center gap-2 text-sm font-medium leading-snug group-data-[disabled=true]/field:opacity-50',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
