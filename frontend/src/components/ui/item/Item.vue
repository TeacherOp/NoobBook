<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const itemVariants = cva(
  'group/item [a]:hover:bg-accent/50 focus-visible:border-ring focus-visible:ring-ring/50 [a]:transition-colors flex flex-wrap items-center rounded-md border border-transparent text-sm outline-none transition-colors duration-100 focus-visible:ring-[3px]',
  {
    variants: {
      variant: {
        default: 'bg-transparent',
        outline: 'border-border',
        muted: 'bg-muted/50',
      },
      size: {
        default: 'gap-4 p-4',
        sm: 'gap-2.5 px-4 py-3',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

type ItemVariants = VariantProps<typeof itemVariants>

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  variant?: ItemVariants['variant']
  size?: ItemVariants['size']
}>(), {
  variant: 'default',
  size: 'default',
})
</script>

<template>
  <div
    data-slot="item"
    :data-variant="props.variant"
    :data-size="props.size"
    :class="cn(itemVariants({ variant: props.variant, size: props.size }), props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
