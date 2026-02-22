<script setup lang="ts">
import { cn } from '@/lib/utils'
import { Separator } from '@/components/ui/separator'

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  orientation?: 'horizontal' | 'vertical'
}>(), {
  orientation: 'vertical',
})
</script>

<template>
  <Separator
    data-slot="button-group-separator"
    :orientation="props.orientation"
    :class="cn(
      'bg-input relative !m-0 self-stretch data-[orientation=vertical]:h-auto',
      props.class
    )"
    v-bind="$attrs"
  />
</template>
