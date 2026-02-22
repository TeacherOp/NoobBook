<script setup lang="ts">
import { PhCircleNotch } from '@phosphor-icons/vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <PhCircleNotch
    :size="16"
    role="status"
    aria-label="Loading"
    :class="cn('animate-spin', props.class)"
    v-bind="$attrs"
  />
</template>
