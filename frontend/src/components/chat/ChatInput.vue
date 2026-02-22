<script setup lang="ts">
/**
 * ChatInput Component
 * Educational Note: Textarea that auto-resizes. Enter sends, Shift+Enter = newline.
 * Voice recording shows partial transcript inline while recording.
 */
import { ref, computed, watch, nextTick } from 'vue'
import { PhPaperPlaneTilt, PhMicrophone, PhCircleNotch } from '@phosphor-icons/vue'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{
  message: string
  partialTranscript: string
  isRecording: boolean
  sending: boolean
  transcriptionConfigured: boolean
}>()

const emit = defineEmits<{
  'update:message': [value: string]
  send: []
  micClick: []
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

// Display combines typed message + partial transcript
const displayMessage = computed(() => {
  if (!props.partialTranscript) return props.message
  const sep = props.message && !props.message.endsWith(' ') ? ' ' : ''
  return props.message + sep + props.partialTranscript
})

// Auto-resize textarea
watch(displayMessage, async () => {
  await nextTick()
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 100)}px`
})

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !props.isRecording) {
    e.preventDefault()
    emit('send')
  }
}

const micTitle = computed(() => {
  if (!props.transcriptionConfigured) return 'Set up ElevenLabs API key in settings'
  if (props.sending) return 'Wait for response to complete'
  if (props.isRecording) return 'Click to stop recording'
  return 'Click to start recording'
})
</script>

<template>
  <div class="p-4 pt-2">
    <div class="flex items-center gap-2 border rounded-2xl px-3 py-2 bg-background">
      <!-- Mic button -->
      <button
        type="button"
        :disabled="props.sending || !props.transcriptionConfigured"
        :title="micTitle"
        class="flex-shrink-0 p-1.5 rounded-full transition-colors"
        :class="[
          props.isRecording ? 'bg-red-500 text-white animate-pulse' : 'text-muted-foreground hover:text-foreground',
          (props.sending || !props.transcriptionConfigured) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
        ]"
        @click="emit('micClick')"
      >
        <PhMicrophone :size="18" />
      </button>

      <!-- Textarea -->
      <Textarea
        ref="textareaRef"
        autofocus
        :placeholder="isRecording
          ? 'Listening...'
          : !transcriptionConfigured
          ? 'Type your message... (voice disabled - set API key)'
          : 'Ask about your sources... (Shift+Enter for new line)'"
        :value="displayMessage"
        :disabled="props.sending || props.isRecording"
        :class="['flex-1 py-1.5 min-h-[32px] max-h-[100px] resize-none border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent', props.partialTranscript ? 'text-muted-foreground' : '']"
        rows="1"
        @input="emit('update:message', ($event.target as HTMLTextAreaElement).value)"
        @keydown="handleKeyDown"
      />

      <!-- Send button -->
      <button
        type="button"
        :disabled="!props.message.trim() || props.sending || props.isRecording"
        class="flex-shrink-0 p-1.5 rounded-full text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        @click="emit('send')"
      >
        <PhCircleNotch v-if="props.sending" :size="18" class="animate-spin" />
        <PhPaperPlaneTilt v-else :size="18" />
      </button>
    </div>

    <p class="text-xs text-muted-foreground mt-2 text-center">
      {{ isRecording
        ? 'Listening... Click mic to stop'
        : !transcriptionConfigured
        ? 'Voice input requires ElevenLabs API key (Admin Settings)'
        : 'Click mic to speak, or type your message' }}
    </p>
  </div>
</template>
