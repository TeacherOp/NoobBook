/**
 * useVoiceRecording Hook
 * Educational Note: Custom hook for ElevenLabs real-time speech-to-text.
 * Extracts all WebSocket and audio capture logic from ChatPanel for reusability.
 *
 * Flow:
 * 1. Fetch fresh config from backend (includes single-use token)
 * 2. Connect to ElevenLabs WebSocket (token is in URL)
 * 3. Wait for session_started event
 * 4. Capture audio via AudioWorklet, convert to PCM, send as base64
 * 5. Receive partial and committed transcripts
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { chatsAPI } from '../../lib/api/chats';
import { createLogger } from '@/lib/logger';

const log = createLogger('voice-recording');

interface UseVoiceRecordingProps {
  onError: (message: string) => void;
  onTranscriptCommit: (text: string) => void;
}

interface UseVoiceRecordingReturn {
  isRecording: boolean;
  partialTranscript: string;
  transcriptionConfigured: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

export const useVoiceRecording = ({
  onError,
  onTranscriptCommit,
}: UseVoiceRecordingProps): UseVoiceRecordingReturn => {
  // State
  const [isRecording, setIsRecording] = useState(false);
  const [partialTranscript, setPartialTranscript] = useState('');
  const [transcriptionConfigured, setTranscriptionConfigured] = useState(false);

  // Refs for audio streaming
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  // Track if a commit was processed to avoid duplicate text insertion
  const commitProcessedRef = useRef<boolean>(false);

  /**
   * Check if ElevenLabs transcription is configured on mount
   */
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const configured = await chatsAPI.isTranscriptionConfigured();
        setTranscriptionConfigured(configured);
      } catch (err) {
        log.error({ err }, 'failed to check transcription status');
        setTranscriptionConfigured(false);
      }
    };
    checkStatus();
  }, []);

  /**
   * Educational Note: Start capturing audio from microphone and stream to WebSocket.
   * Uses AudioWorklet for efficient real-time processing without blocking the main thread.
   *
   * ElevenLabs expects audio as JSON messages with base64-encoded PCM data:
   * { message_type: "input_audio_chunk", audio_base_64: "...", sample_rate: 16000 }
   */
  const startAudioCapture = useCallback(async (sampleRate: number) => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: sampleRate,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      // Create AudioContext with target sample rate
      const audioContext = new AudioContext({ sampleRate });
      audioContextRef.current = audioContext;

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
      `;

      const blob = new Blob([workletCode], { type: 'application/javascript' });
      const url = URL.createObjectURL(blob);

      await audioContext.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);

      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');
      workletNodeRef.current = workletNode;

      // Send audio data to WebSocket as base64-encoded JSON
      workletNode.port.onmessage = (event) => {
        const ws = websocketRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
          // Convert ArrayBuffer to base64
          const bytes = new Uint8Array(event.data);
          let binary = '';
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const audioBase64 = btoa(binary);

          // Send as JSON message (ElevenLabs format)
          ws.send(JSON.stringify({
            message_type: 'input_audio_chunk',
            audio_base_64: audioBase64,
            sample_rate: sampleRate,
          }));
        }
      };

      source.connect(workletNode);
      // Don't connect to destination (we don't want to hear ourselves)

      log.debug('audio capture started');
    } catch (err) {
      log.error({ err }, 'failed to start audio capture');
      onError('Failed to access microphone. Please check permissions.');
      stopRecording();
    }
  }, [onError]);

  /**
   * Educational Note: Start real-time transcription with ElevenLabs WebSocket.
   */
  const startRecording = useCallback(async () => {
    try {
      // Reset commit tracking for new recording session
      commitProcessedRef.current = false;

      // Always fetch fresh config (token is single-use and expires)
      log.debug('fetching transcription config');
      const config = await chatsAPI.getTranscriptionConfig();
      log.debug('connecting to WebSocket');

      // Connect to ElevenLabs WebSocket (token is in the URL)
      const ws = new WebSocket(config.websocket_url);
      websocketRef.current = ws;

      ws.onopen = () => {
        log.debug('WebSocket connected, waiting for session_started');
        // Don't start audio capture yet - wait for session_started
      };

      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          log.debug(`WS message: ${data.message_type || data.type}`);

          // Educational Note: ElevenLabs uses message_type field
          const messageType = data.message_type || data.type;

          if (messageType === 'session_started') {
            log.debug('session started, beginning audio capture');
            // Now start audio capture
            await startAudioCapture(config.sample_rate);
          } else if (messageType === 'partial_transcript' && data.text) {
            setPartialTranscript(data.text);
          } else if (messageType === 'committed_transcript' && data.text) {
            // Mark that a commit was processed (prevents duplicate in stopRecording fallback)
            commitProcessedRef.current = true;
            // Send committed text to parent
            onTranscriptCommit(data.text);
            setPartialTranscript('');
          } else if (messageType === 'auth_error') {
            log.error({ error: data.error }, 'ElevenLabs auth error');
            onError('Authentication error: ' + (data.error || 'Invalid token'));
            stopRecording();
          } else if (messageType === 'error' || messageType === 'input_error') {
            log.error({ data }, 'ElevenLabs transcription error');
            onError('Transcription error: ' + (data.error || data.message || 'Unknown error'));
          }
        } catch (err) {
          log.error({ err }, 'failed to parse WebSocket message');
        }
      };

      ws.onerror = () => {
        log.error('WebSocket connection error');
        onError('Connection error. Please try again.');
        stopRecording();
      };

      ws.onclose = () => {
        log.debug('WebSocket closed');
      };

      setIsRecording(true);
    } catch (err) {
      log.error({ err }, 'failed to start recording');
      onError('Failed to start transcription. Check API key in settings.');
    }
  }, [onError, onTranscriptCommit, startAudioCapture]);

  /**
   * Stop recording and clean up resources
   */
  const stopRecording = useCallback(() => {
    // Stop audio capture first
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Close WebSocket with commit
    if (websocketRef.current) {
      // Educational Note: Send a manual commit before closing to ensure
      // any remaining audio is transcribed. Without this, partial transcripts
      // would be lost if user stops before VAD detects silence.
      if (websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.send(JSON.stringify({
          message_type: 'input_audio_chunk',
          audio_base_64: '',
          commit: true,
          sample_rate: 16000,
        }));

        // Give a moment for committed_transcript to arrive before closing
        // Also save partial transcript as fallback (only if commit wasn't processed)
        const currentPartial = partialTranscript;
        setTimeout(() => {
          // Only add partial if no committed_transcript was received (fallback)
          if (currentPartial && !commitProcessedRef.current) {
            log.debug('commit not processed, using partial fallback');
            onTranscriptCommit(currentPartial);
            setPartialTranscript('');
          }

          if (websocketRef.current) {
            websocketRef.current.close();
            websocketRef.current = null;
          }
        }, 500);
      } else {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    }

    // If there's a partial transcript and WebSocket was already closed, save it
    // (only if commit wasn't already processed)
    if (partialTranscript && !websocketRef.current && !commitProcessedRef.current) {
      onTranscriptCommit(partialTranscript);
      setPartialTranscript('');
    }

    setIsRecording(false);
    log.debug('recording stopped');
  }, [partialTranscript, onTranscriptCommit]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      if (workletNodeRef.current) {
        workletNodeRef.current.disconnect();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return {
    isRecording,
    partialTranscript,
    transcriptionConfigured,
    startRecording,
    stopRecording,
  };
};
