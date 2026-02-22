<script setup lang="ts">
/**
 * AudioSection — Audio Overview generation
 * Registers generation handler with studio context on mount.
 * Manages playback state for the shared <audio> element.
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { toast } from 'vue-sonner'
import { useStudioContext, useFilteredJobs } from '@/composables/useStudio'
import { audioAPI, type AudioJob } from '@/lib/api/studio'
import { api } from '@/lib/api/client'
import type { StudioSignal } from '@/lib/types/studio'
import { createLogger } from '@/lib/logger'
import AudioListItem from './AudioListItem.vue'
import GenericProgressIndicator from '../shared/GenericProgressIndicator.vue'
import { PhHeadphones } from '@phosphor-icons/vue'

const log = createLogger('audio-section')
const { projectId, registerGenerationHandler } = useStudioContext()

// Jobs
const savedJobs = ref<AudioJob[]>([])
const currentJob = ref<AudioJob | null>(null)
const isGenerating = ref(false)
const filteredJobs = useFilteredJobs(savedJobs)

// Playback state
const audioEl = ref<HTMLAudioElement | null>(null)
const playingJobId = ref<string | null>(null)
const isPaused = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const playbackRate = ref(1)
const SPEEDS = [1, 1.25, 1.5, 1.75, 2] as const

async function loadSavedJobs() {
  const res = await audioAPI.listJobs(projectId)
  if (res.success && res.jobs)
    savedJobs.value = res.jobs.filter(j => j.status === 'ready')
}

async function handleGeneration(signal: StudioSignal) {
  const sourceId = signal.sources[0]?.source_id
  if (!sourceId) { toast.error('No source specified for audio generation.'); return }

  isGenerating.value = true
  currentJob.value = null
  try {
    const ttsStatus = await audioAPI.checkTTSStatus()
    if (!ttsStatus.configured) {
      toast.error('ElevenLabs API key not configured. Please add it in Admin Settings.')
      return
    }
    const start = await audioAPI.startGeneration(projectId, sourceId, signal.direction)
    if (!start.success || !start.job_id) { toast.error(start.error || 'Failed to start audio generation.'); return }

    toast.success(`Generating audio for ${start.source_name}...`)
    const finalJob = await audioAPI.pollJobStatus(projectId, start.job_id, j => { currentJob.value = j })

    if (finalJob.status === 'ready') {
      toast.success('Your audio overview is ready to play!')
      savedJobs.value = [finalJob, ...savedJobs.value]
    } else {
      toast.error(finalJob.error || 'Audio generation failed.')
    }
  } catch (err) {
    log.error({ err }, 'audio generation failed')
    toast.error('Audio generation failed.')
  } finally {
    isGenerating.value = false
    currentJob.value = null
  }
}

onMounted(() => {
  loadSavedJobs()
  audioEl.value = new Audio()
  audioEl.value.addEventListener('ended', () => { playingJobId.value = null; isPaused.value = false; currentTime.value = 0; duration.value = 0 })
  audioEl.value.addEventListener('timeupdate', () => { currentTime.value = audioEl.value?.currentTime ?? 0 })
  audioEl.value.addEventListener('loadedmetadata', () => { duration.value = audioEl.value?.duration ?? 0; if (audioEl.value) audioEl.value.playbackRate = playbackRate.value })
})

onUnmounted(() => { audioEl.value?.pause() })


registerGenerationHandler('audio_overview', handleGeneration)

function playAudio(job: AudioJob) {
  if (!job.audio_url || !audioEl.value) return
  if (playingJobId.value === job.id && isPaused.value) {
    audioEl.value.play(); isPaused.value = false; return
  }
  if (playingJobId.value !== job.id) { audioEl.value.pause(); currentTime.value = 0; duration.value = 0 }
  audioEl.value.src = job.audio_url
  audioEl.value.play()
  playingJobId.value = job.id
  isPaused.value = false
}

function pauseAudio() { audioEl.value?.pause(); isPaused.value = true }

function seekTo(time: number) {
  if (audioEl.value) { audioEl.value.currentTime = time; currentTime.value = time }
}

function cyclePlaybackRate() {
  const idx = SPEEDS.indexOf(playbackRate.value as typeof SPEEDS[number])
  const next = SPEEDS[(idx + 1) % SPEEDS.length]
  playbackRate.value = next
  if (audioEl.value) audioEl.value.playbackRate = next
}

async function downloadAudio(job: AudioJob) {
  if (!job.audio_url) return
  try {
    const res = await api.get(job.audio_url, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url; a.download = job.audio_filename || 'audio_overview.mp3'; a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    log.error({ err }, 'audio download failed')
    toast.error('Failed to download audio.')
  }
}

function formatDuration(secs: number) {
  const m = Math.floor(secs / 60), s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
</script>

<template>
  <template v-if="filteredJobs.length > 0 || isGenerating">
    <GenericProgressIndicator
      v-if="isGenerating"
      :title="currentJob?.source_name || 'Generating audio...'"
      :subtitle="currentJob?.progress || 'Starting...'"
      :icon="PhHeadphones"
    />
    <AudioListItem
      v-for="job in filteredJobs"
      :key="job.id"
      :job="job"
      :playing-job-id="playingJobId"
      :is-paused="isPaused"
      :current-time="currentTime"
      :duration="duration"
      :playback-rate="playbackRate"
      :format-duration="formatDuration"
      @play="playAudio"
      @pause="pauseAudio"
      @seek="seekTo"
      @cycle-speed="cyclePlaybackRate"
      @download="downloadAudio"
    />
  </template>
</template>
