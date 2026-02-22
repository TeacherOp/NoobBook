/**
 * useVoiceRecording Composable
 *
 * Educational Note: Vue equivalent of the React useVoiceRecording hook.
 * Handles ElevenLabs real-time speech-to-text via WebSocket + AudioWorklet.
 *
 * The WebSocket and AudioWorklet code is vanilla JS — only the reactive
 * state wrapper changed from React (useState/useRef) to Vue (ref).
 *
 * Flow:
 * 1. Fetch fresh config from backend (includes single-use token)
 * 2. Connect to ElevenLabs WebSocket (token is in URL)
 * 3. Wait for session_started event
 * 4. Capture audio via AudioWorklet, convert to PCM, send as base64
 * 5. Receive partial and committed transcripts
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { chatsAPI } from '@/lib/api/chats'
import { createLogger } from '@/lib/logger'

const log = createLogger('voice-recording')

interface UseVoiceRecordingProps {
  onError: (message: string) => void
  onTranscriptCommit: (text: string) => void
}

export function useVoiceRecording({ onError, onTranscriptCommit }: UseVoiceRecordingProps) {
  // Reactive state
  const isRecording = ref(false)
  const partialTranscript = ref('')
  const transcriptionConfigured = ref(false)

  // Non-reactive refs for audio streaming (no need to trigger re-renders)
  let audioContext: AudioContext | null = null
  let mediaStream: MediaStream | null = null
  let workletNode: AudioWorkletNode | null = null
  let websocket: WebSocket | null = null
  let commitProcessed = false

  /**
   * Check if ElevenLabs transcription is configured on mount
   */
  onMounted(async () => {
    try {
      const configured = await chatsAPI.isTranscriptionConfigured()
      transcriptionConfigured.value = configured
    } catch (err) {
      log.error({ err }, 'failed to check transcription status')
      transcriptionConfigured.value = false
    }
  })

  /**
   * Educational Note: Start capturing audio from microphone and stream to WebSocket.
   * Uses AudioWorklet for efficient real-time processing without blocking the main thread.
   *
   * ElevenLabs expects audio as JSON messages with base64-encoded PCM data:
   * { message_type: "input_audio_chunk", audio_base_64: "...", sample_rate: 16000 }
   */
  async function startAudioCapture(sampleRate: number) {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: sampleRate,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      mediaStream = stream

      // Create AudioContext with target sample rate
      const ctx = new AudioContext({ sampleRate })
      audioContext = ctx

      // Educational Note: AudioWorklet processes audio in a separate thread.
      // It converts Float32 to Int16 PCM and sends to main thread.
      const workletCode = `
        class PCMProcessor extends AudioWorkletProcessor {
          constructor() {
            super();
            this.buffer = [];
            this.bufferSize = 4096; // ~0.25 sec at 16kHz
          }

          process(inputs) {
            const input = inputs[0];
            if (input && input[0]) {
              // Convert Float32 (-1 to 1) to Int16 PCM
              const float32 = input[0];
              for (let i = 0; i < float32.length; i++) {
                const s = Math.max(-1, Math.min(1, float32[i]));
                const int16 = s < 0 ? s * 0x8000 : s * 0x7FFF;
                this.buffer.push(int16);
              }

              // Send when buffer is full
              if (this.buffer.length >= this.bufferSize) {
                const int16Array = new Int16Array(this.buffer);
                this.port.postMessage(int16Array.buffer, [int16Array.buffer]);
                this.buffer = [];
              }
            }
            return true;
          }
        }
        registerProcessor('pcm-processor', PCMProcessor);
      `

      const blob = new Blob([workletCode], { type: 'application/javascript' })
      const url = URL.createObjectURL(blob)

      await ctx.audioWorklet.addModule(url)
      URL.revokeObjectURL(url)

      const source = ctx.createMediaStreamSource(stream)
      const node = new AudioWorkletNode(ctx, 'pcm-processor')
      workletNode = node

      // Send audio data to WebSocket as base64-encoded JSON
      node.port.onmessage = (event) => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          // Convert ArrayBuffer to base64
          const bytes = new Uint8Array(event.data)
          let binary = ''
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i])
          }
          const audioBase64 = btoa(binary)

          // Send as JSON message (ElevenLabs format)
          websocket.send(JSON.stringify({
            message_type: 'input_audio_chunk',
            audio_base_64: audioBase64,
            sample_rate: sampleRate,
          }))
        }
      }

      source.connect(node)
      // Don't connect to destination (we don't want to hear ourselves)

      log.debug('audio capture started')
    } catch (err) {
      log.error({ err }, 'failed to start audio capture')
      onError('Failed to access microphone. Please check permissions.')
      stopRecording()
    }
  }

  /**
   * Educational Note: Start real-time transcription with ElevenLabs WebSocket.
   */
  async function startRecording() {
    try {
      // Reset commit tracking for new recording session
      commitProcessed = false

      // Always fetch fresh config (token is single-use and expires)
      log.debug('fetching transcription config')
      const config = await chatsAPI.getTranscriptionConfig()
      log.debug('connecting to WebSocket')

      // Connect to ElevenLabs WebSocket (token is in the URL)
      const ws = new WebSocket(config.websocket_url)
      websocket = ws

      ws.onopen = () => {
        log.debug('WebSocket connected, waiting for session_started')
      }

      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data)
          log.debug(`WS message: ${data.message_type || data.type}`)

          const messageType = data.message_type || data.type

          if (messageType === 'session_started') {
            log.debug('session started, beginning audio capture')
            await startAudioCapture(config.sample_rate)
          } else if (messageType === 'partial_transcript' && data.text) {
            partialTranscript.value = data.text
          } else if (messageType === 'committed_transcript' && data.text) {
            commitProcessed = true
            onTranscriptCommit(data.text)
            partialTranscript.value = ''
          } else if (messageType === 'auth_error') {
            log.error({ error: data.error }, 'ElevenLabs auth error')
            onError('Authentication error: ' + (data.error || 'Invalid token'))
            stopRecording()
          } else if (messageType === 'error' || messageType === 'input_error') {
            log.error({ data }, 'ElevenLabs transcription error')
            onError('Transcription error: ' + (data.error || data.message || 'Unknown error'))
          }
        } catch (err) {
          log.error({ err }, 'failed to parse WebSocket message')
        }
      }

      ws.onerror = () => {
        log.error('WebSocket connection error')
        onError('Connection error. Please try again.')
        stopRecording()
      }

      ws.onclose = () => {
        log.debug('WebSocket closed')
      }

      isRecording.value = true
    } catch (err) {
      log.error({ err }, 'failed to start recording')
      onError('Failed to start transcription. Check API key in settings.')
    }
  }

  /**
   * Stop recording and clean up resources
   */
  function stopRecording() {
    // Stop audio capture first
    if (workletNode) {
      workletNode.disconnect()
      workletNode = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop())
      mediaStream = null
    }

    // Close WebSocket with commit
    if (websocket) {
      // Educational Note: Send a manual commit before closing to ensure
      // any remaining audio is transcribed. Without this, partial transcripts
      // would be lost if user stops before VAD detects silence.
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
          message_type: 'input_audio_chunk',
          audio_base_64: '',
          commit: true,
          sample_rate: 16000,
        }))

        // Give a moment for committed_transcript to arrive before closing
        const currentPartial = partialTranscript.value
        setTimeout(() => {
          if (currentPartial && !commitProcessed) {
            log.debug('commit not processed, using partial fallback')
            onTranscriptCommit(currentPartial)
            partialTranscript.value = ''
          }

          if (websocket) {
            websocket.close()
            websocket = null
          }
        }, 500)
      } else {
        websocket.close()
        websocket = null
      }
    }

    // If there's a partial transcript and WebSocket was already closed, save it
    if (partialTranscript.value && !websocket && !commitProcessed) {
      onTranscriptCommit(partialTranscript.value)
      partialTranscript.value = ''
    }

    isRecording.value = false
    log.debug('recording stopped')
  }

  // Cleanup on unmount
  onUnmounted(() => {
    if (websocket) websocket.close()
    if (workletNode) workletNode.disconnect()
    if (audioContext) audioContext.close()
    if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop())
  })

  return {
    isRecording,
    partialTranscript,
    transcriptionConfigured,
    startRecording,
    stopRecording,
  }
}
