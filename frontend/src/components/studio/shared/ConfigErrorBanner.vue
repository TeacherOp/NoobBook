<script setup lang="ts">
import { PhWarningCircle } from '@phosphor-icons/vue'
defineProps<{ message: string | null }>()
</script>

<template>
  <div v-if="message" class="p-2.5 bg-amber-500/10 rounded-md border border-amber-500/30">
    <div class="flex items-start gap-2">
      <PhWarningCircle :size="16" weight="fill" class="text-amber-500 flex-shrink-0 mt-0.5" />
      <div class="flex-1 min-w-0">
        <p class="text-xs font-medium text-amber-700">API Key Required</p>
        <p class="text-[11px] text-amber-600/80 mt-0.5">{{ message }}</p>
      </div>
    </div>
  </div>
</template>
