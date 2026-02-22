<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  variant?: 'legend' | 'label'
}>(), {
  variant: 'legend',
})
</script>

<template>
  <legend
    data-slot="field-legend"
    :data-variant="props.variant"
    :class="cn(
      'mb-3 font-medium',
      'data-[variant=legend]:text-base',
      'data-[variant=label]:text-sm',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </legend>
</template>
