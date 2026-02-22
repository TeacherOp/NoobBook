<script setup lang="ts">
import { cn } from '@/lib/utils'
import { Separator } from '@/components/ui/separator'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <Separator
    data-slot="item-separator"
    orientation="horizontal"
    :class="cn('my-0', props.class)"
    v-bind="$attrs"
  />
</template>
