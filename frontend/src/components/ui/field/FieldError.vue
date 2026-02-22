<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  class?: string
  errors?: Array<{ message?: string } | undefined>
}>()

const slots = defineSlots<{ default?: () => any }>()

const hasContent = computed(() => {
  if (slots.default) return true
  if (!props.errors?.length) return false
  return props.errors.some(e => e?.message)
})
</script>

<template>
  <div
    v-if="hasContent"
    role="alert"
    data-slot="field-error"
    :class="cn('text-destructive text-sm font-normal', props.class)"
    v-bind="$attrs"
  >
    <slot>
      <template v-if="errors?.length === 1 && errors[0]?.message">
        {{ errors[0].message }}
      </template>
      <ul v-else class="ml-4 flex list-disc flex-col gap-1">
        <template v-for="(error, index) in errors" :key="index">
          <li v-if="error?.message">{{ error.message }}</li>
        </template>
      </ul>
    </slot>
  </div>
</template>
