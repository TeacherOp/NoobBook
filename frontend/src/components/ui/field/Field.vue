<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const fieldVariants = cva(
  'group/field data-[invalid=true]:text-destructive flex w-full gap-3',
  {
    variants: {
      orientation: {
        vertical: ['flex-col [&>*]:w-full [&>.sr-only]:w-auto'],
        horizontal: [
          'flex-row items-center',
          '[&>[data-slot=field-label]]:flex-auto',
          'has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px has-[>[data-slot=field-content]]:items-start',
        ],
        responsive: [
          '@md/field-group:flex-row @md/field-group:items-center @md/field-group:[&>*]:w-auto flex-col [&>*]:w-full [&>.sr-only]:w-auto',
          '@md/field-group:[&>[data-slot=field-label]]:flex-auto',
          '@md/field-group:has-[>[data-slot=field-content]]:items-start @md/field-group:has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px',
        ],
      },
    },
    defaultVariants: {
      orientation: 'vertical',
    },
  }
)

type FieldVariants = VariantProps<typeof fieldVariants>

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  class?: string
  orientation?: FieldVariants['orientation']
}>(), {
  orientation: 'vertical',
})
</script>

<template>
  <div
    role="group"
    data-slot="field"
    :data-orientation="props.orientation"
    :class="cn(fieldVariants({ orientation: props.orientation }), props.class)"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
