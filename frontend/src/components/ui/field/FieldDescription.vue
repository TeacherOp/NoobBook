<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <p
    data-slot="field-description"
    :class="cn(
      'text-muted-foreground text-sm font-normal leading-normal group-has-[[data-orientation=horizontal]]/field:text-balance',
      'nth-last-2:-mt-1 last:mt-0 [[data-variant=legend]+&]:-mt-1.5',
      '[&>a:hover]:text-primary [&>a]:underline [&>a]:underline-offset-4',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </p>
</template>
