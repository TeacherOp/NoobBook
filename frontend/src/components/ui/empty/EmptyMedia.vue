<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const emptyMediaVariants = cva(
  'mb-2 flex shrink-0 items-center justify-center [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-transparent',
        icon: 'bg-muted text-foreground flex size-10 shrink-0 items-center justify-center rounded-lg [&_svg:not([class*=\'size-\'])]:size-6',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

type EmptyMediaVariants = VariantProps<typeof emptyMediaVariants>

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  variant?: EmptyMediaVariants['variant']
}>(), {
  variant: 'default',
})
</script>

<template>
  <div
    data-slot="empty-icon"
    :data-variant="props.variant"
    :class="cn(emptyMediaVariants({ variant: props.variant }), props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
