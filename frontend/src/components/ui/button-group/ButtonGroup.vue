<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonGroupVariants = cva(
  'flex w-fit items-stretch has-[>[data-slot=button-group]]:gap-2 [&>*]:focus-visible:relative [&>*]:focus-visible:z-10 has-[select[aria-hidden=true]:last-child]:[&>[data-slot=select-trigger]:last-of-type]:rounded-r-md [&>[data-slot=select-trigger]:not([class*=\'w-\'])]:w-fit [&>input]:flex-1',
  {
    variants: {
      orientation: {
        horizontal:
          '[&>*:not(:first-child)]:rounded-l-none [&>*:not(:first-child)]:border-l-0 [&>*:not(:last-child)]:rounded-r-none',
        vertical:
          'flex-col [&>*:not(:first-child)]:rounded-t-none [&>*:not(:first-child)]:border-t-0 [&>*:not(:last-child)]:rounded-b-none',
      },
    },
    defaultVariants: {
      orientation: 'horizontal',
    },
  }
)

type GroupVariants = VariantProps<typeof buttonGroupVariants>

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  orientation?: GroupVariants['orientation']
}>(), {
  orientation: 'horizontal',
})
</script>

<template>
  <div
    role="group"
    data-slot="button-group"
    :data-orientation="props.orientation"
    :class="cn(buttonGroupVariants({ orientation: props.orientation }), props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
