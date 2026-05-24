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
  CircleNotch,
  PaperPlaneTilt,
  Microphone,
  CodeBlock,
  StopCircle,
  Image as ImageIcon,
  X,
} from '@phosphor-icons/react';
import { usePermissions } from '@/contexts/PermissionsContext';
import { optimizeAttachment } from '@/lib/image/optimizeAttachment';

const ATTACHMENT_ALLOWED_MIMES = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'image/gif',
]);
// Pre-optimize ceiling. We accept raw inputs up to this size, then the
// optimizer reduces them. A 20 MB Retina PNG that decodes to <1 MB is
// fine; the cap exists so a 200 MB drag-drop doesn't hang the browser
// decoder. The 5 MB final cap is below as POST_OPTIMIZE_MAX_BYTES.
const ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024;
// Mirrors backend `_MAX_ATTACHMENT_BYTES` in messages/routes.py. After
// optimization we re-validate against this; a hand-crafted huge file
// that survives compression would be rejected here.
const POST_OPTIMIZE_MAX_BYTES = 5 * 1024 * 1024;
const ATTACHMENT_MAX_COUNT = 10;
// Debounce window before showing the "Optimising image…" indicator.
// Most paste/drag-drop ops finish well under this, so the indicator
// only appears for genuinely large inputs — keeps the UX flashy for
// small images.
const COMPRESSING_INDICATOR_DELAY_MS = 250;

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

  // Surface "Optimising image…" only when the optimizer takes longer
  // than COMPRESSING_INDICATOR_DELAY_MS — small pastes finish well
  // under that and we don't want a flash of UI per attachment.
  const [compressing, setCompressing] = useState(false);

  // Ref-mirror of the current attachments array so the async path in
  // `acceptFiles` reads the freshest list AFTER its `await`. Without
  // this, two overlapping paste/drop gestures both captured the same
  // initial `attachments` snapshot inside the closure and the second
  // `onAttachmentsChange` overwrote the first — silently dropping
  // the first batch. The ref is updated every render via the
  // sync-effect below so it always reflects the parent's latest
  // state by the time the await resolves.
  const attachmentsRef = useRef(attachments);
  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

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
    async (incoming: File[]) => {
      if (!incoming.length) return;

      // MIME + raw-size gate. Pre-optimize cap is generous (20 MB) so
      // large screenshots survive the gate and reach the optimizer.
      const preOptimized: File[] = [];
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
            `${file.name || 'Image'} is over the 20MB upload cap.`,
          );
          continue;
        }
        preOptimized.push(file);
      }
      if (!preOptimized.length) return;

      // Show the indicator only if the optimizer is slow enough that
      // the user would notice. `setTimeout` returns a handle we clear
      // unconditionally in the finally block so a fast path never
      // flashes the indicator.
      const indicatorTimer = window.setTimeout(
        () => setCompressing(true),
        COMPRESSING_INDICATOR_DELAY_MS,
      );

      let optimized: File[];
      try {
        optimized = await Promise.all(
          preOptimized.map((f) => optimizeAttachment(f)),
        );
      } finally {
        window.clearTimeout(indicatorTimer);
        setCompressing(false);
      }

      // Post-optimize re-validation against the backend cap. Catches
      // a hand-crafted huge file that survived the optimizer (or one
      // whose alpha-channel forced a PNG retention without enough
      // resize headroom).
      const accepted: File[] = [];
      for (const file of optimized) {
        if (file.size > POST_OPTIMIZE_MAX_BYTES) {
          onAttachmentError?.(
            `${file.name || 'Image'} didn't compress small enough — try a smaller image.`,
          );
          continue;
        }
        accepted.push(file);
      }
      if (!accepted.length) return;

      // Read the latest attachments list via the ref — the `attachments`
      // prop captured in this closure is the snapshot from the render
      // that fired off this acceptFiles call; if a second paste/drop
      // started while the first was still in `await Promise.all`,
      // using the prop would clobber the first batch.
      const current = attachmentsRef.current;
      const next = [...current, ...accepted];
      if (next.length > ATTACHMENT_MAX_COUNT) {
        onAttachmentError?.(
          `Maximum ${ATTACHMENT_MAX_COUNT} attachments per message — extras dropped.`,
        );
      }
      const merged = next.slice(0, ATTACHMENT_MAX_COUNT);
      // Update the ref synchronously so a *third* concurrent call sees
      // this merge result, not the parent state that hasn't committed
      // yet. React's setState is async; the ref is the only single
      // source of truth across overlapping awaits.
      attachmentsRef.current = merged;
      onAttachmentsChange(merged);
    },
    [onAttachmentsChange, onAttachmentError],
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
  // Why: preventDefault must run unconditionally on dragenter/dragover or
  // the browser refuses the drop entirely. We can't gate on
  // `dataTransfer.types` including 'Files' here because some browsers
  // (and most Linux file managers) only expose that flag on drop, not
  // during dragover — checking it caused drag-drop to silently no-op.
  // acceptFiles() filters by MIME, so non-image drops are still rejected
  // cleanly with a toast.
  const hasFiles = (e: React.DragEvent) =>
    Array.from(e.dataTransfer.types || []).includes('Files');

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (hasFiles(e)) setDragDepth((d) => d + 1);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (hasFiles(e)) setDragDepth((d) => Math.max(0, d - 1));
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

        {compressing && (
          // Debounced — only renders if optimization is taking long
          // enough that the user would otherwise wonder why the chip
          // hasn't appeared yet. Stays well clear of the textarea.
          <div className="flex items-center gap-2 px-3 pt-2 text-[11px] text-muted-foreground">
            <CircleNotch size={12} className="animate-spin" />
            <span>Optimising image…</span>
          </div>
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
            // `resize-y` exposes the native bottom-right drag handle so
            // users can pull the box taller when they're drafting longer
            // messages. min/max bound it so the input can't shrink to a
            // single line or swallow the entire chat surface.
            className={`flex-1 py-1.5 min-h-[32px] max-h-[400px] resize-y border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent ${
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
