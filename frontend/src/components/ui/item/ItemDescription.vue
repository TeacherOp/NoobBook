<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <p
    data-slot="item-description"
    :class="cn(
      'text-muted-foreground line-clamp-2 text-balance text-sm font-normal leading-normal',
      '[&>a:hover]:text-primary [&>a]:underline [&>a]:underline-offset-4',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </p>
</template>
