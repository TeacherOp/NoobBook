<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const inputGroupButtonVariants = cva(
  'flex items-center gap-2 text-sm shadow-none',
  {
    variants: {
      size: {
        xs: 'h-6 gap-1 rounded-[calc(var(--radius)-5px)] px-2 has-[>svg]:px-2 [&>svg:not([class*=\'size-\'])]:size-3.5',
        sm: 'h-8 gap-1.5 rounded-md px-2.5 has-[>svg]:px-2.5',
        'icon-xs': 'size-6 rounded-[calc(var(--radius)-5px)] p-0 has-[>svg]:p-0',
        'icon-sm': 'size-8 p-0 has-[>svg]:p-0',
      },
    },
    defaultVariants: {
      size: 'xs',
    },
  }
)

type ButtonSizeVariants = VariantProps<typeof inputGroupButtonVariants>

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  type?: string
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'soft' | 'brand' | 'ghost' | 'link'
  size?: ButtonSizeVariants['size']
}>(), {
  type: 'button',
  variant: 'ghost',
  size: 'xs',
})
</script>

<template>
  <Button
    :type="props.type"
    :data-size="props.size"
    :variant="props.variant"
    :class="cn(inputGroupButtonVariants({ size: props.size }), props.class)"
    v-bind="$attrs"
  >
    <slot />
  </Button>
</template>
