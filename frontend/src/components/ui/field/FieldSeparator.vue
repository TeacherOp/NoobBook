<script setup lang="ts">
import { cn } from '@/lib/utils'
import { Separator } from '@/components/ui/separator'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
const slots = defineSlots<{ default?: () => any }>()
</script>

<template>
  <div
    data-slot="field-separator"
    :data-content="!!slots.default"
    :class="cn(
      'relative -my-2 h-5 text-sm group-data-[variant=outline]/field-group:-mb-2',
      props.class
    )"
    v-bind="$attrs"
  >
    <Separator class="absolute inset-0 top-1/2" />
    <span
      v-if="slots.default"
      class="bg-background text-muted-foreground relative mx-auto block w-fit px-2"
      data-slot="field-separator-content"
    >
      <slot />
    </span>
  </div>
</template>
