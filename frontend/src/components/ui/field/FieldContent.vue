<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <div
    data-slot="field-content"
    :class="cn('group/field-content flex flex-1 flex-col gap-1.5 leading-snug', props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
