<script setup lang="ts">
import { computed } from 'vue'
import { PhSpeakerHigh, PhPlay, PhPause, PhDownloadSimple } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import type { AudioJob } from '@/lib/api/studio'

const props = defineProps<{
  job: AudioJob
  playingJobId: string | null
  isPaused: boolean
  currentTime: number
  duration: number
  playbackRate: number
  formatDuration: (s: number) => string
}>()

const emit = defineEmits<{
  play: [job: AudioJob]
  pause: []
  seek: [time: number]
  cycleSpeed: []
  download: [job: AudioJob]
}>()

const isActive = computed(() => props.playingJobId === props.job.id)
const isPlaying = computed(() => isActive.value && !props.isPaused)

function handleSeek(e: Event) {
  emit('seek', parseFloat((e.target as HTMLInputElement).value))
}

const seekBackground = computed(() => {
  if (!props.duration) return undefined
  const pct = (props.currentTime / props.duration) * 100
  return `linear-gradient(to right, hsl(var(--primary)) ${pct}%, hsl(var(--primary) / 0.2) ${pct}%)`
})
</script>

<template>
  <div class="flex flex-col gap-1.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors">
    <div class="flex items-center gap-2.5">
      <div class="p-1.5 bg-primary/10 rounded-md flex-shrink-0 w-7 h-7 flex items-center justify-center">
        <div v-if="isPlaying" class="flex items-end gap-[2px] h-4">
          <span class="audio-bar w-[3px]" />
          <span class="audio-bar w-[3px]" />
          <span class="audio-bar w-[3px]" />
          <span class="audio-bar w-[3px]" />
        </div>
        <PhSpeakerHigh v-else :size="16" class="text-primary" />
      </div>
      <div class="flex-1 min-w-0 overflow-hidden">
        <p class="text-xs font-medium truncate">{{ job.source_name }}</p>
      </div>
      <div class="flex items-center gap-1 flex-shrink-0">
        <Button
          size="sm"
          :variant="isActive ? 'default' : 'ghost'"
          class="h-7 w-7 p-0"
          @click="isPlaying ? emit('pause') : emit('play', job)"
        >
          <PhPause v-if="isPlaying" :size="16" weight="fill" />
          <PhPlay v-else :size="16" weight="fill" />
        </Button>
        <Button size="sm" variant="ghost" class="h-7 w-7 p-0" @click="emit('download', job)">
          <PhDownloadSimple :size="16" />
        </Button>
      </div>
    </div>

    <!-- Timeline (visible when active) -->
    <div v-if="isActive" class="flex items-center gap-2 px-1">
      <span class="text-[11px] text-muted-foreground tabular-nums w-[34px] text-right flex-shrink-0">
        {{ formatDuration(currentTime) }}
      </span>
      <input
        type="range"
        :min="0"
        :max="duration || 0"
        :value="currentTime"
        step="0.1"
        class="audio-seekbar flex-1"
        :style="seekBackground ? { background: seekBackground } : {}"
        @input="handleSeek"
      />
      <span class="text-[11px] text-muted-foreground tabular-nums w-[34px] flex-shrink-0">
        {{ formatDuration(duration) }}
      </span>
      <button
        class="text-[11px] font-semibold text-primary hover:text-primary/80 tabular-nums flex-shrink-0 px-1"
        @click="emit('cycleSpeed')"
      >
        {{ playbackRate }}x
      </button>
    </div>
  </div>
</template>
