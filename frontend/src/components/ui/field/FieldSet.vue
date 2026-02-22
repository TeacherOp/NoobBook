<script setup lang="ts">
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: string }>()
</script>

<template>
  <fieldset
    data-slot="field-set"
    :class="cn(
      'flex flex-col gap-6',
      'has-[>[data-slot=checkbox-group]]:gap-3 has-[>[data-slot=radio-group]]:gap-3',
      props.class
    )"
    v-bind="$attrs"
  >
    <slot />
  </fieldset>
</template>
