<script setup lang="ts">
import { computed } from 'vue'
import { PhWarningCircle } from '@phosphor-icons/vue'
import { Progress } from '@/components/ui/progress'
import { formatFileSize, MAX_SOURCES } from '@/lib/api/sources'

const props = defineProps<{
  sourcesCount: number
  totalSize: number
}>()

const isAtLimit = computed(() => props.sourcesCount >= MAX_SOURCES)
const progressValue = computed(() => (props.sourcesCount / MAX_SOURCES) * 100)
</script>

<template>
  <div class="px-4 pb-4 space-y-2">
    <div class="flex items-center justify-between text-xs text-muted-foreground">
      <span>{{ sourcesCount }} / {{ MAX_SOURCES }} sources</span>
      <span>{{ formatFileSize(totalSize) }} total</span>
    </div>
    <Progress :model-value="progressValue" class="h-1" />
    <p v-if="isAtLimit" class="text-xs text-destructive flex items-center gap-1">
      <PhWarningCircle :size="12" />
      Source limit reached
    </p>
  </div>
</template>
