/**
 * ChatInput Component
 * Educational Note: Input area with microphone button for voice input,
 * text field for typing, and send button. Displays partial transcripts
 * in real-time while recording. Also accepts inline image attachments
 * via paste, drag-and-drop, or the image button — Claude/Gemini-style.
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Textarea } from '../ui/textarea';
import {
  PaperPlaneTilt,
  Microphone,
  CodeBlock,
  StopCircle,
  Image as ImageIcon,
  X,
} from '@phosphor-icons/react';
import { usePermissions } from '@/contexts/PermissionsContext';

const ATTACHMENT_ALLOWED_MIMES = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'image/gif',
]);
const ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024; // 5MB — Claude vision cap
const ATTACHMENT_MAX_COUNT = 10;

interface ChatInputProps {
  message: string;
  partialTranscript: string;
  isRecording: boolean;
  sending: boolean;
  transcriptionConfigured: boolean;
  rawMode: boolean;
  attachments: File[];
  onMessageChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onMicClick: () => void;
  onToggleRawMode: () => void;
  onAttachmentsChange: (files: File[]) => void;
  // Surface upload-validation errors to the parent's toast system rather
  // than alert() — keeps the warm editorial UX the rest of the app uses.
  onAttachmentError?: (message: string) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  message,
  partialTranscript,
  isRecording,
  sending,
  transcriptionConfigured,
  rawMode,
  attachments,
  onMessageChange,
  onSend,
  onStop,
  onMicClick,
  onToggleRawMode,
  onAttachmentsChange,
  onAttachmentError,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { hasPermission } = usePermissions();
  const canUseVoice = hasPermission('chat_features', 'voice_input');

  // Track drag-active state for the overlay. Counter, not boolean — when
  // the user drags over a child element, dragenter/dragleave fire on
  // each transition; a counter survives those without flickering.
  const [dragDepth, setDragDepth] = useState(0);
  const dragActive = dragDepth > 0;

  // Display value combines typed message and partial transcript
  const displayMessage = partialTranscript
    ? message + (message && !message.endsWith(' ') ? ' ' : '') + partialTranscript
    : message;

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const frameId = requestAnimationFrame(() => {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 100)}px`;
    });
    return () => cancelAnimationFrame(frameId);
  }, [displayMessage]);

  const acceptFiles = useCallback(
    (incoming: File[]) => {
      if (!incoming.length) return;
      const accepted: File[] = [];
      for (const file of incoming) {
        const mime = (file.type || '').toLowerCase();
        if (!ATTACHMENT_ALLOWED_MIMES.has(mime)) {
          onAttachmentError?.(
            `Unsupported format: ${file.name || 'file'}. Use PNG, JPEG, WebP, or GIF.`,
          );
          continue;
        }
        if (file.size > ATTACHMENT_MAX_BYTES) {
          onAttachmentError?.(
            `${file.name || 'Image'} is over the 5MB limit.`,
          );
          continue;
        }
        accepted.push(file);
      }
      if (!accepted.length) return;
      const next = [...attachments, ...accepted];
      if (next.length > ATTACHMENT_MAX_COUNT) {
        onAttachmentError?.(
          `Maximum ${ATTACHMENT_MAX_COUNT} attachments per message — extras dropped.`,
        );
      }
      onAttachmentsChange(next.slice(0, ATTACHMENT_MAX_COUNT));
    },
    [attachments, onAttachmentsChange, onAttachmentError],
  );

  // Paste handler — clipboard images get pulled out as Files. We
  // preventDefault on file items so the browser doesn't paste a binary
  // blob string into the textarea.
  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      if (!e.clipboardData) return;
      const files: File[] = [];
      for (const item of Array.from(e.clipboardData.items)) {
        if (item.kind !== 'file') continue;
        if (!item.type.startsWith('image/')) continue;
        const f = item.getAsFile();
        if (f) files.push(f);
      }
      if (!files.length) return;
      e.preventDefault();
      acceptFiles(files);
    },
    [acceptFiles],
  );

  // Drag-and-drop handlers on the wrapping pill container.
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    if (!Array.from(e.dataTransfer.types || []).includes('Files')) return;
    e.preventDefault();
    setDragDepth((d) => d + 1);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (!Array.from(e.dataTransfer.types || []).includes('Files')) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (!Array.from(e.dataTransfer.types || []).includes('Files')) return;
    e.preventDefault();
    setDragDepth((d) => Math.max(0, d - 1));
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragDepth(0);
      const files = Array.from(e.dataTransfer.files || []);
      acceptFiles(files);
    },
    [acceptFiles],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isRecording) {
      e.preventDefault();
      onSend();
    }
  };

  const removeAttachment = (idx: number) => {
    onAttachmentsChange(attachments.filter((_, i) => i !== idx));
  };

  // Send-enabled logic: text OR attachments OR both — no longer text-only.
  const sendDisabled = (!message.trim() && attachments.length === 0) || isRecording;

  return (
    <div className="p-4 pt-2">
      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative rounded-2xl border bg-background transition-colors ${
          dragActive
            ? 'border-amber-500 ring-2 ring-amber-200 ring-offset-1'
            : 'border-border'
        }`}
      >
        {/* Drag-active overlay — soft amber, non-blocking pointer events. */}
        {dragActive && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-amber-50/85 pointer-events-none">
            <span className="text-sm font-medium text-amber-700">
              Drop image to attach
            </span>
          </div>
        )}

        {attachments.length > 0 && (
          <AttachmentStrip
            attachments={attachments}
            onRemove={removeAttachment}
          />
        )}

        {/* Floating pill — mic, textarea, image, raw, send. */}
        <div className="flex items-center gap-2 px-3 py-2">
          {/* Microphone Button */}
          {canUseVoice && (
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
              } ${
                sending || !transcriptionConfigured
                  ? 'opacity-50 cursor-not-allowed'
                  : 'cursor-pointer'
              }`}
            >
              <Microphone size={18} />
            </button>
          )}

          {/* Image attach button — opens a hidden file input. Mirrors the
              mic-button visual pattern so the input chrome stays balanced. */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={sending || isRecording || attachments.length >= ATTACHMENT_MAX_COUNT}
            title={
              attachments.length >= ATTACHMENT_MAX_COUNT
                ? `Max ${ATTACHMENT_MAX_COUNT} attachments`
                : 'Attach image (or paste / drag from desktop)'
            }
            className={`flex-shrink-0 p-1.5 rounded-full transition-colors text-muted-foreground hover:text-foreground ${
              sending || isRecording || attachments.length >= ATTACHMENT_MAX_COUNT
                ? 'opacity-50 cursor-not-allowed'
                : 'cursor-pointer'
            }`}
          >
            <ImageIcon size={18} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/webp,image/gif"
            multiple
            className="hidden"
            onChange={(e) => {
              const picked = Array.from(e.target.files || []);
              acceptFiles(picked);
              // Reset so picking the same file twice in a row still fires onChange.
              e.target.value = '';
            }}
          />

          {/* Textarea */}
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
            onPaste={handlePaste}
            className={`flex-1 py-1.5 min-h-[32px] max-h-[100px] resize-none border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent ${
              partialTranscript ? 'text-muted-foreground' : ''
            }`}
            disabled={sending || isRecording}
            rows={1}
          />

          {/* Raw Mode Toggle */}
          <button
            type="button"
            onClick={onToggleRawMode}
            title={rawMode ? 'Switch to normal view' : 'Switch to raw message view'}
            className={`flex-shrink-0 p-1.5 rounded-full transition-colors ${
              rawMode
                ? 'bg-amber-600 text-white'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <CodeBlock size={18} weight={rawMode ? 'bold' : 'regular'} />
          </button>

          {/* Send / Stop */}
          {sending ? (
            <button
              type="button"
              onClick={onStop}
              title="Stop responding"
              className="flex-shrink-0 p-1.5 rounded-full text-red-500 hover:text-red-600 hover:bg-red-50 transition-colors"
            >
              <StopCircle size={18} weight="fill" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onSend}
              disabled={sendDisabled}
              className="flex-shrink-0 p-1.5 rounded-full text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <PaperPlaneTilt size={18} />
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground mt-2 text-center">
        {!canUseVoice
          ? 'Type, paste, or drop an image'
          : isRecording
          ? 'Listening... Click mic to stop'
          : !transcriptionConfigured
          ? 'Voice input requires ElevenLabs API key (Admin Settings)'
          : 'Click mic to speak, type, paste, or drop an image'}
      </p>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────
// AttachmentStrip — thumbnails for pasted/dropped images, with X-to-remove
// ──────────────────────────────────────────────────────────────────────

interface AttachmentStripProps {
  attachments: File[];
  onRemove: (index: number) => void;
}

const AttachmentStrip: React.FC<AttachmentStripProps> = ({
  attachments,
  onRemove,
}) => {
  // Derive blob URLs synchronously via useMemo (no setState-in-effect
  // antipattern), and use a separate effect ONLY for the revoke-on-
  // change cleanup so the browser frees the underlying buffer once the
  // user sends, removes, or unmounts.
  const previews = useMemo(
    () => attachments.map((f) => URL.createObjectURL(f)),
    [attachments],
  );
  useEffect(() => {
    return () => {
      previews.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [previews]);

  if (!attachments.length) return null;

  return (
    <div className="flex items-center gap-2 px-3 pt-2 overflow-x-auto">
      {attachments.map((file, idx) => (
        <div
          key={`${file.name}-${idx}`}
          className="relative flex-shrink-0 group"
          title={`${file.name} · ${formatBytes(file.size)}`}
        >
          <img
            src={previews[idx]}
            alt={file.name}
            className="h-16 w-16 rounded-md object-cover border border-border"
          />
          <button
            type="button"
            onClick={() => onRemove(idx)}
            className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-stone-800/85 text-white flex items-center justify-center opacity-90 hover:opacity-100 transition-opacity"
            title="Remove"
            aria-label={`Remove ${file.name}`}
          >
            <X size={12} weight="bold" />
          </button>
        </div>
      ))}
    </div>
  );
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
