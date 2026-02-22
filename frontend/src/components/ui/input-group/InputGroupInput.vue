<script setup lang="ts">
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <Input
    data-slot="input-group-control"
    :class="cn(
      'flex-1 rounded-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent',
      props.class
    )"
    v-bind="$attrs"
  />
</template>
