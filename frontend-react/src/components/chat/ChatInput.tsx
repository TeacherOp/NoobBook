/**
 * ChatInput Component
 * Educational Note: Input area with microphone button for voice input,
 * text field for typing, and send button. Displays partial transcripts
 * in real-time while recording.
 */

import React, { useRef, useEffect } from 'react';
import { Textarea } from '../ui/textarea';
import { PaperPlaneTilt, Microphone, CircleNotch } from '@phosphor-icons/react';

interface ChatInputProps {
  message: string;
  partialTranscript: string;
  isRecording: boolean;
  sending: boolean;
  transcriptionConfigured: boolean;
  onMessageChange: (value: string) => void;
  onSend: () => void;
  onMicClick: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  message,
  partialTranscript,
  isRecording,
  sending,
  transcriptionConfigured,
  onMessageChange,
  onSend,
  onMicClick,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Display value combines typed message and partial transcript
  const displayMessage = partialTranscript
    ? message + (message && !message.endsWith(' ') ? ' ' : '') + partialTranscript
    : message;

  // Auto-resize textarea based on content
  // Educational Note: Wrapping in requestAnimationFrame batches both height changes
  // (reset to 'auto' + set to scrollHeight) into a single paint cycle, preventing
  // visible cursor flicker / layout reflow on every keystroke.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const frameId = requestAnimationFrame(() => {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 100)}px`;
    });

    return () => cancelAnimationFrame(frameId);
  }, [displayMessage]);

  // Handle key down - Enter sends, Shift+Enter adds new line
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isRecording) {
      e.preventDefault(); // Prevent new line
      onSend();
    }
    // Shift+Enter will naturally add a new line (default textarea behavior)
  };

  return (
    <div className="p-4 pt-2">
      {/* Floating pill container - mic, textarea, send all inside */}
      <div className="flex items-center gap-2 border rounded-2xl px-3 py-2 bg-background">
        {/* Microphone Button - seamlessly integrated */}
        <button
          type="button"
          onClick={onMicClick}
          disabled={sending || !transcriptionConfigured}
          title={
            !transcriptionConfigured
              ? 'Set up ElevenLabs API key in settings'
              : sending
              ? 'Wait for response to complete'
              : isRecording
              ? 'Click to stop recording'
              : 'Click to start recording'
          }
          className={`flex-shrink-0 p-1.5 rounded-full transition-colors ${
            isRecording
              ? 'bg-red-500 text-white animate-pulse'
              : 'text-muted-foreground hover:text-foreground'
          } ${sending || !transcriptionConfigured ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <Microphone size={18} />
        </button>

        {/* Textarea - no border, blends with container */}
        <Textarea
          ref={textareaRef}
          autoFocus
          placeholder={
            isRecording
              ? 'Listening...'
              : !transcriptionConfigured
              ? 'Type your message... (voice disabled - set API key)'
              : 'Ask about your sources... (Shift+Enter for new line)'
          }
          value={displayMessage}
          onChange={(e) => onMessageChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className={`flex-1 py-1.5 min-h-[32px] max-h-[100px] resize-none border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent ${
            partialTranscript ? 'text-muted-foreground' : ''
          }`}
          disabled={sending || isRecording}
          rows={1}
        />

        {/* Send Button - seamlessly integrated */}
        <button
          type="button"
          onClick={onSend}
          disabled={!message.trim() || sending || isRecording}
          className="flex-shrink-0 p-1.5 rounded-full text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {sending ? (
            <CircleNotch size={18} className="animate-spin" />
          ) : (
            <PaperPlaneTilt size={18} />
          )}
        </button>
      </div>

      <p className="text-xs text-muted-foreground mt-2 text-center">
        {isRecording
          ? 'Listening... Click mic to stop'
          : !transcriptionConfigured
          ? 'Voice input requires ElevenLabs API key (Admin Settings)'
          : 'Click mic to speak, or type your message'}
      </p>
    </div>
  );
};
