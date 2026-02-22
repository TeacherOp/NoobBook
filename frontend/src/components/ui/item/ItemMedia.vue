<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const itemMediaVariants = cva(
  'flex shrink-0 items-center justify-center gap-2 group-has-[[data-slot=item-description]]/item:translate-y-0.5 group-has-[[data-slot=item-description]]/item:self-start [&_svg]:pointer-events-none',
  {
    variants: {
      variant: {
        default: 'bg-transparent',
        icon: 'bg-muted size-8 rounded-sm border [&_svg:not([class*=\'size-\'])]:size-4',
        image: 'size-10 overflow-hidden rounded-sm [&_img]:size-full [&_img]:object-cover',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

type MediaVariants = VariantProps<typeof itemMediaVariants>

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  variant?: MediaVariants['variant']
}>(), {
  variant: 'default',
})
</script>

<template>
  <div
    data-slot="item-media"
    :data-variant="props.variant"
    :class="cn(itemMediaVariants({ variant: props.variant }), props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
