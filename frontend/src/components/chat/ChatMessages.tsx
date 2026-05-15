/**
 * ChatMessages Component
 * Educational Note: Displays the conversation message list with user and AI messages.
 * - User messages: Right-aligned, simple styling
 * - AI messages: Left-aligned with markdown rendering and citation support
 * - Citations appear as hoverable badges that show source content
 * - Shows a loading indicator when waiting for AI response
 */

import React, { useRef, useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Ghost, FileText, Copy, Check, DownloadSimple, ArrowDown } from '@phosphor-icons/react';
import type { Message } from '../../lib/api/chats';
import { messageContentAsText } from '../../lib/api/chats';
import { parseCitations } from '../../lib/citations';
import { CitationBadge } from './CitationBadge';
import { Separator } from '../ui/separator';
import { sourcesAPI } from '../../lib/api/sources';
import { getAuthUrl } from '../../lib/api/client';
import { Button } from '../ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import { copyToClipboard } from '@/lib/clipboard';
import { createLogger } from '@/lib/logger';
import { cn } from '@/lib/utils';

const log = createLogger('chat-messages');

/**
 * Format a message timestamp for display next to the bubble.
 *
 * Today  → "3:45 PM"
 * This year, different day → "May 11, 3:45 PM"
 * Different year          → "May 11, 2025, 3:45 PM"
 *
 * Invalid / missing timestamps return an empty string so the caller can
 * skip rendering without an extra guard.
 */
const formatMessageTime = (raw?: string): string => {
  if (!raw) return '';
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return '';

  const now = new Date();
  const timePart = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return timePart;

  const sameYear = d.getFullYear() === now.getFullYear();
  const datePart = d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  });
  return `${datePart}, ${timePart}`;
};

const MessageTimestamp: React.FC<{ raw?: string; align: 'left' | 'right' }> = ({ raw, align }) => {
  const formatted = formatMessageTime(raw);
  if (!formatted) return null;
  return (
    <p
      className={cn(
        'mt-1 text-[11px] text-muted-foreground/80 select-none',
        align === 'right' ? 'text-right' : 'text-left'
      )}
      // Surface full ISO on hover so users can copy exact time if needed —
      // the visible form is intentionally short to keep the chat tidy.
      title={raw}
    >
      {formatted}
    </p>
  );
};

interface ChatMessagesProps {
  messages: Message[];
  sending: boolean;
  projectId: string;
  streamingAssistantContent?: string;
  /**
   * Live progress message emitted by the running tool (e.g. the
   * Freshdesk analyzer announces "Running ticket query…" between SSE
   * deltas). When set, the ReadingIndicator shows this instead of the
   * generic rotating "Untangling the question…" phrases — concrete
   * progress beats whimsy when the user is waiting 30+ seconds.
   */
  toolProgress?: string;
  /**
   * Render in read-only mode (used by the shared-project view). Currently
   * a no-op for write affordances inside this component (the input + stop
   * live in ChatPanel), but accepted for API symmetry and reserved for
   * future hide-actions toggles.
   */
  readOnly?: boolean;
  /**
   * Rewrites image / asset URLs before they reach the markdown renderer.
   * The shared-project view uses this to swap owner-only studio asset
   * URLs (`/api/v1/projects/:pid/studio/...`) for share-token proxy URLs
   * (`/api/v1/share/:token/studio/...`) so anonymous viewers can load the
   * artifacts.
   */
  studioAssetRewriter?: (url: string) => string;
}

/**
 * Shared markdown component configurations
 * Educational Note: These define how different markdown elements are rendered.
 * Extracted as a constant to be reused across text segments.
 * Using 'as const' and explicit any typing for react-markdown compatibility.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const markdownComponents: Record<string, React.FC<any>> = {
  // Headers
  h1: ({ children }: { children: React.ReactNode }) => (
    <h1 className="text-lg font-bold mt-4 mb-2 first:mt-0">{children}</h1>
  ),
  h2: ({ children }: { children: React.ReactNode }) => (
    <h2 className="text-base font-bold mt-4 mb-2 first:mt-0">{children}</h2>
  ),
  h3: ({ children }: { children: React.ReactNode }) => (
    <h3 className="text-sm font-bold mt-3 mb-1 first:mt-0">{children}</h3>
  ),
  // Paragraphs - inline-block allows citations to sit next to text
  p: ({ children }: { children: React.ReactNode }) => (
    <p className="text-sm mb-2 last:mb-0">{children}</p>
  ),
  // Lists
  ul: ({ children }: { children: React.ReactNode }) => (
    <ul className="text-sm list-disc pl-4 mb-2 space-y-1">{children}</ul>
  ),
  ol: ({ children }: { children: React.ReactNode }) => (
    <ol className="text-sm list-decimal pl-4 mb-2 space-y-1">{children}</ol>
  ),
  li: ({ children }: { children: React.ReactNode }) => (
    <li className="text-sm">{children}</li>
  ),
  // Code blocks
  code: ({ className, children, ...props }: { className?: string; children: React.ReactNode }) => {
    const content = String(children).replace(/\n$/, '');
    const hasNewlines = content.includes('\n');
    const isBlock = className || hasNewlines;

    if (!isBlock) {
      return (
        <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono break-all">
          {children}
        </code>
      );
    }
    return (
      <code className="text-xs font-mono whitespace-pre" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }: { children: React.ReactNode }) => (
    <pre className="my-2 overflow-x-auto max-w-full !bg-stone-900 !text-stone-100 p-3 rounded-lg">
      {children}
    </pre>
  ),
  // Links
  a: ({ href, children }: { href?: string; children: React.ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline hover:no-underline break-all"
    >
      {children}
    </a>
  ),
  // Bold and italic
  strong: ({ children }: { children: React.ReactNode }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  em: ({ children }: { children: React.ReactNode }) => (
    <em className="italic">{children}</em>
  ),
  // Blockquotes
  blockquote: ({ children }: { children: React.ReactNode }) => (
    <blockquote className="border-l-2 border-primary/50 pl-3 italic text-muted-foreground my-2">
      {children}
    </blockquote>
  ),
  // Horizontal rule
  hr: () => <hr className="border-border my-4" />,
  // Tables
  table: ({ children }: { children: React.ReactNode }) => (
    <div className="overflow-x-auto my-3 max-w-full">
      <table className="min-w-full text-sm border-collapse border border-border rounded-lg">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }: { children: React.ReactNode }) => (
    <thead className="bg-muted/70">{children}</thead>
  ),
  tbody: ({ children }: { children: React.ReactNode }) => (
    <tbody className="divide-y divide-border">{children}</tbody>
  ),
  tr: ({ children }: { children: React.ReactNode }) => (
    <tr className="hover:bg-muted/30">{children}</tr>
  ),
  th: ({ children }: { children: React.ReactNode }) => (
    <th className="px-3 py-2 text-left font-semibold border-b border-border">
      {children}
    </th>
  ),
  td: ({ children }: { children: React.ReactNode }) => (
    <td className="px-3 py-2 border-b border-border">{children}</td>
  ),
  // Images
  img: ({ src, alt }: { src?: string; alt?: string }) => (
    <img
      src={src}
      alt={alt || ''}
      className="max-w-full h-auto rounded-lg my-2"
    />
  ),
  // Strikethrough
  del: ({ children }: { children: React.ReactNode }) => (
    <del className="line-through text-muted-foreground">{children}</del>
  ),
};

/**
 * User Message Component
 * Educational Note: Right-aligned bubble style for user messages.
 * Content is either a plain string (legacy / no-attachment) or a list of
 * typed blocks `[{type:"image", url, ...}, {type:"text", text}]` when the
 * user pasted/dropped images. Image blocks render as thumbnails above
 * the text inside the same bubble.
 */
type UserMessageBlock =
  | { type: 'image'; url: string; media_type?: string; filename?: string }
  | { type: 'text'; text: string };

const UserMessage: React.FC<{ content: string | UserMessageBlock[] }> = ({ content }) => {
  const isBlocks = Array.isArray(content);
  const imageBlocks = isBlocks
    ? (content as UserMessageBlock[]).filter((b): b is Extract<UserMessageBlock, { type: 'image' }> => b.type === 'image')
    : [];
  const textValue = isBlocks
    ? (content as UserMessageBlock[])
        .filter((b): b is Extract<UserMessageBlock, { type: 'text' }> => b.type === 'text')
        .map((b) => b.text)
        .join('\n')
    : (content as string);

  return (
    <div className="flex justify-end w-full">
      <div className="max-w-[80%] min-w-0">
        <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2 min-w-0 space-y-2">
          {imageBlocks.length > 0 && (
            <div className="flex flex-wrap gap-2 -mx-1">
              {imageBlocks.map((block, idx) => (
                <a
                  key={`${block.url}-${idx}`}
                  href={block.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  // Open in a new tab so the user can see the full image.
                  // Bubble cap of ~240px keeps the chat compact.
                  className="block"
                  title={block.filename || 'attachment'}
                >
                  <img
                    src={block.url}
                    alt={block.filename || 'attachment'}
                    className="max-h-60 max-w-full rounded-lg object-cover border border-primary-foreground/20"
                  />
                </a>
              ))}
            </div>
          )}
          {textValue && (
            <p className="text-sm whitespace-pre-wrap break-words">{textValue}</p>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * AI Message Component
 * Educational Note: Left-aligned with full markdown rendering support.
 * Now handles citations with [[cite:CHUNK_ID]] format.
 * Chunk ID format: {source_id}_page_{page}_chunk_{n}
 *
 * Citation Strategy:
 * 1. Pre-process content: Convert [[cite:chunk_id]] to markdown links [#N](cite:chunk_id)
 * 2. Render through single ReactMarkdown instance (preserves inline flow)
 * 3. Custom 'a' component detects cite: links and renders CitationBadge
 */
interface AIMessageProps {
  content: string;
  projectId: string;
  studioAssetRewriter?: (url: string) => string;
}

/**
 * Message Action Buttons Component
 * Educational Note: Copy and Download buttons for AI messages,
 * similar to ChatGPT/Gemini UX pattern.
 */
interface MessageActionsProps {
  content: string;
}

const MessageActions: React.FC<MessageActionsProps> = ({ content }) => {
  const [copied, setCopied] = useState(false);

  /**
   * Copy message content to clipboard
   * Educational Note: Uses modern Clipboard API with visual feedback
   */
  const handleCopy = async () => {
    // Strip citation markers ([[cite:...]]) so the copied text reads cleanly
    // outside the app — they're rendered as badges, not literal text.
    const cleanContent = content.replace(/\[\[cite:[^\]]+\]\]/g, '');

    const ok = await copyToClipboard(cleanContent);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else {
      log.error('failed to copy text');
    }
  };

  /**
   * Download message as markdown file
   * Educational Note: Creates a blob and triggers download
   */
  const handleDownload = () => {
    // Remove citation markers for cleaner downloaded text
    const cleanContent = content.replace(/\[\[cite:[^\]]+\]\]/g, '');
    const blob = new Blob([cleanContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `response-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <TooltipProvider>
      <div className="flex items-center gap-1 mt-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
            >
              {copied ? (
                <Check size={16} weight="bold" className="text-green-600" />
              ) : (
                <Copy size={16} weight="bold" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <p className="text-xs">{copied ? 'Copied!' : 'Copy'}</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDownload}
              className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
            >
              <DownloadSimple size={16} weight="bold" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <p className="text-xs">Download</p>
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
};

const AIMessage: React.FC<AIMessageProps> = ({ content, projectId, studioAssetRewriter }) => {
  // Parse citations from content to get citation numbers
  const { uniqueCitations, markerToNumber } = useMemo(
    () => parseCitations(content),
    [content]
  );

  // Pre-process content: Convert citations and images to markdown format
  const processedContent = useMemo(() => {
    let processed = content;

    // Replace citation markers with markdown hash links
    // [[cite:CHUNK_ID]] -> [N](#cite-CHUNK_ID)
    // CHUNK_ID format: {source_id}_page_{page}_chunk_{n}
    processed = processed.replace(
      /\[\[cite:([a-zA-Z0-9_-]+_page_\d+_chunk_\d+)\]\]/g,
      (match, chunkId) => {
        const citationNumber = markerToNumber.get(match) || 0;
        return `[${citationNumber}](#cite-${chunkId})`;
      }
    );

    // Replace image markers with markdown images
    // [[image:FILENAME]] -> ![Chart](URL)
    // Educational Note: AI agents generate charts/plots saved to ai_outputs/images
    processed = processed.replace(
      /\[\[image:([^\]]+)\]\]/g,
      (_match, filename) => {
        const imageUrl = sourcesAPI.getAIImageUrl(projectId, filename);
        return `![${filename}](${getAuthUrl(imageUrl)})`;
      }
    );

    return processed;
  }, [content, markerToNumber, projectId]);

  // Create markdown components with citation-aware link handler
  const componentsWithCitations = useMemo(() => ({
    ...markdownComponents,
    // Rewrite asset URLs (studio outputs etc.) when a rewriter is supplied —
    // used by the shared-project view to redirect owner-only paths through
    // the share-token proxy.
    img: ({ src, alt }: { src?: string; alt?: string }) => (
      <img
        src={src ? (studioAssetRewriter ? studioAssetRewriter(src) : src) : src}
        alt={alt || ''}
        className="max-w-full h-auto rounded-lg my-2"
      />
    ),
    // Override 'a' to handle citation links
    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => {
      // Check if this is a citation link (#cite-CHUNK_ID)
      // Using hash URLs prevents browser navigation
      if (href) {
        // Match hash citation format: #cite-{source_id}_page_{page}_chunk_{n}
        const citeMatch = href.match(/#cite-(.+_page_(\d+)_chunk_\d+)$/);
        if (citeMatch) {
          const chunkId = citeMatch[1];
          const pageNumber = parseInt(citeMatch[2], 10);
          // Extract source_id from chunk_id (everything before _page_)
          const sourceId = chunkId.split('_page_')[0];
          const citationNumber = typeof children === 'string' ? parseInt(children, 10) : 0;
          return (
            <CitationBadge
              citationNumber={citationNumber}
              chunkId={chunkId}
              sourceId={sourceId}
              pageNumber={pageNumber}
              projectId={projectId}
            />
          );
        }
      }
      // Regular link
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary underline hover:no-underline break-all"
        >
          {children}
        </a>
      );
    },
  }), [projectId, studioAssetRewriter]);

  return (
    <div className="flex justify-start w-full max-w-full overflow-hidden">
      <div className="max-w-[85%] min-w-0 flex gap-3 overflow-hidden">
        <div className="flex-shrink-0 mt-1">
          <Ghost size={28} weight="bold" className="text-primary hover:scale-110 hover:rotate-6 transition-transform duration-200 cursor-pointer" />
        </div>
        <div className="bg-muted/50 rounded-2xl rounded-tl-sm px-4 py-3 min-w-0 overflow-hidden flex-1">
          <p className="text-xs font-medium text-muted-foreground mb-2">NoobBook</p>

          {/* Single ReactMarkdown instance - preserves inline flow */}
          <div className="prose prose-sm prose-stone max-w-none min-w-0 overflow-hidden prose-pre:bg-stone-900 prose-pre:text-stone-100 prose-code:text-stone-100 prose-code:bg-transparent">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={componentsWithCitations}
            >
              {processedContent}
            </ReactMarkdown>
          </div>

          {/* Sources footer - only show if there are citations */}
          {uniqueCitations.length > 0 && (
            <>
              <Separator className="my-3" />
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                  <FileText size={12} />
                  <span>Sources</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {uniqueCitations.map((citation) => (
                    <div
                      key={`footer-${citation.citationNumber}`}
                      className="text-xs text-muted-foreground"
                    >
                      <span className="font-medium">[{citation.citationNumber}]</span>
                      {' '}Page {citation.pageNumber}
                      {citation.chunkIndex > 1 && `, Section ${citation.chunkIndex}`}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Action buttons - Copy & Download */}
          <MessageActions content={content} />
        </div>
      </div>
    </div>
  );
};

/**
 * Reading Beat — assistant "thinking" indicator.
 *
 * Replaces the generic three-bouncing-dots pattern with a Claude-style
 * rotating phrase reel that matches NoobBook's literary character: the AI is
 * a reader before it's a writer. The first beat is always "Reading your
 * message…" (the literal action that just happened), then if the SSE delta
 * still hasn't landed the indicator rotates through a curated pool of
 * editorial phrases — each evoking the act of close reading.
 *
 * The amber underscan sweeping left→right is the signature beat — a finger
 * tracing across a printed page. Unmounts the moment streamingAssistantContent
 * becomes non-empty (parent's existing render condition handles the swap).
 */
const READING_OPENER = 'Reading your message';
const THINKING_PHRASES = [
  'Thinking it through',
  'Tracing the threads',
  'Marking up the margins',
  'Cross-referencing sources',
  'Considering the angles',
  'Gathering thoughts',
  'Turning it over',
  'Sketching a reply',
  'Mulling on it',
  'Connecting the dots',
  'Weighing the evidence',
  'Untangling the question',
];

const PHASE_INTERVAL_MS = 2200;
const OPENER_HOLD_MS = 1600;

const ReadingIndicator: React.FC<{ progressMessage?: string }> = ({ progressMessage }) => {
  // Shuffle the pool once per mount so each chat feels fresh; keep ordering
  // stable across phase ticks within the same waiting window. We use a
  // lazy-init useState rather than useMemo because shuffling pulls
  // Math.random — the React compiler flags impure calls inside useMemo,
  // but the lazy initializer is the canonical "run once at mount" hook.
  const [queue] = useState(() => {
    const pool = [...THINKING_PHRASES];
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    return pool;
  });

  const [step, setStep] = useState(0); // 0 = opener, 1+ = queue[step-1]

  // Pause the rotating phrases when a real tool_progress is being shown
  // — flipping a poetic phrase out of view every 2.2s while a concrete
  // status sits in its place would feel jittery. The phrase resumes
  // rotating from where it left off once the tool message clears.
  useEffect(() => {
    if (progressMessage) return;
    const tick = window.setTimeout(
      () => setStep((s) => s + 1),
      step === 0 ? OPENER_HOLD_MS : PHASE_INTERVAL_MS,
    );
    return () => window.clearTimeout(tick);
  }, [step, progressMessage]);

  // Trim the ellipsis so the trailing animated dots aren't doubled.
  // Backend emits "Running ticket query…" and we append our own dots.
  const trimmedProgress = progressMessage?.replace(/[….]+$/, '').trim();
  const phrase = trimmedProgress
    ? trimmedProgress
    : step === 0 ? READING_OPENER : queue[(step - 1) % queue.length];

  return (
    <div
      className="flex justify-start"
      style={{ animation: 'reading-bubble-in 220ms ease-out both' }}
      role="status"
      aria-live="polite"
      aria-label={`${phrase}…`}
    >
      <div className="max-w-[85%] flex gap-3">
        <div
          className="flex-shrink-0 mt-1"
          style={{ animation: 'reading-breathe 2.4s ease-in-out infinite' }}
        >
          <Ghost size={28} weight="bold" className="text-primary" />
        </div>
        <div className="relative overflow-hidden rounded-2xl rounded-tl-sm bg-muted/50 px-4 py-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">NoobBook</p>
          <p
            key={step}
            className="font-serif text-[15px] italic leading-snug text-stone-600"
            style={{ animation: 'reading-bubble-in 320ms ease-out both' }}
          >
            {phrase}
            <span className="ml-0.5 inline-flex">
              <span className="animate-[reading-breathe_1.4s_ease-in-out_infinite]">.</span>
              <span className="animate-[reading-breathe_1.4s_ease-in-out_0.2s_infinite]">.</span>
              <span className="animate-[reading-breathe_1.4s_ease-in-out_0.4s_infinite]">.</span>
            </span>
          </p>
          {/* Underscan: a finger tracing across a page. */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px overflow-hidden">
            <div
              className="h-full w-1/3 bg-gradient-to-r from-transparent via-amber-500/70 to-transparent"
              style={{ animation: 'reading-scan 2.4s ease-in-out infinite' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * ChatMessages Component - Memoized to prevent re-renders on parent state changes
 * Educational Note: Without React.memo, every keystroke in ChatInput would
 * re-render this entire component (expensive markdown parsing). Memoization
 * ensures it only re-renders when messages, sending, or projectId actually change.
 */
export const ChatMessages: React.FC<ChatMessagesProps> = React.memo(({
  messages,
  sending,
  projectId,
  streamingAssistantContent = '',
  toolProgress,
  readOnly: _readOnly,
  studioAssetRewriter,
}) => {
  // _readOnly is reserved for future use; ChatMessages currently has no
  // write affordances of its own (input + stop live in ChatPanel).
  void _readOnly;
  const containerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Track if user has manually scrolled away from bottom
  const userScrolledAwayRef = useRef(false);

  // Mirror of userScrolledAwayRef for rendering the "Jump to latest" reading
  // marker — refs don't trigger re-renders, so we keep a state copy that the
  // scroll handler updates only on threshold crossings (not every pixel).
  const [showJumpMarker, setShowJumpMarker] = useState(false);

  // Track previous message count to detect initial load
  const prevMessageCountRef = useRef(0);

  /**
   * Smart Auto-Scroll Logic
   * - On initial load (messages go from 0 to N): always scroll to bottom
   * - On new messages: only scroll if user hasn't scrolled away
   * - This respects users who scroll up to read history
   */
  useEffect(() => {
    const isInitialLoad = prevMessageCountRef.current === 0 && messages.length > 0;

    // Always scroll on initial load, otherwise only if user is at bottom
    if (isInitialLoad) {
      // Instant scroll for initial load (no animation needed)
      messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
      userScrolledAwayRef.current = false;
    } else if (!userScrolledAwayRef.current) {
      // Smooth scroll for new messages when user is at bottom
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    prevMessageCountRef.current = messages.length;
  }, [messages, sending, streamingAssistantContent]);

  // Track when user scrolls away from bottom
  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    // User is "scrolled away" if more than 150px from bottom
    // User is "back at bottom" if within 50px (with some tolerance)
    if (distanceFromBottom > 150) {
      userScrolledAwayRef.current = true;
      if (!showJumpMarker) setShowJumpMarker(true);
    } else if (distanceFromBottom < 50) {
      userScrolledAwayRef.current = false;
      if (showJumpMarker) setShowJumpMarker(false);
    }
  };

  const jumpToLatest = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    userScrolledAwayRef.current = false;
    setShowJumpMarker(false);
  };

  return (
    <div className="relative flex-1 min-h-0 min-w-0 w-full bg-white">
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="absolute inset-0 overflow-y-auto overflow-x-hidden"
    >
      <div className="pt-6 pb-2 px-6 space-y-4 w-full">
        {messages.filter((msg) => msg && msg.id).map((msg) => (
          <div key={msg.id}>
            {msg.role === 'user' ? (
              <UserMessage content={msg.content} />
            ) : (
              // AI messages don't carry image blocks today; coerce to
              // string so the markdown renderer's prop type stays simple.
              <AIMessage
                content={messageContentAsText(msg.content)}
                projectId={projectId}
                studioAssetRewriter={studioAssetRewriter}
              />
            )}
            <MessageTimestamp raw={msg.timestamp} align={msg.role === 'user' ? 'right' : 'left'} />
            {msg.error && (
              <p className="text-xs text-destructive text-center mt-1">
                This message had an error
              </p>
            )}
          </div>
        ))}

        {streamingAssistantContent && (
          <AIMessage
            content={streamingAssistantContent}
            projectId={projectId}
            studioAssetRewriter={studioAssetRewriter}
          />
        )}

        {/* Reading Beat — fills the gap between Send and first SSE delta.
            If the running tool is emitting tool_progress events, show
            those instead of the rotating poetic phrases. */}
        {sending && !streamingAssistantContent && (
          <ReadingIndicator progressMessage={toolProgress} />
        )}

        {/* Invisible element to scroll to */}
        <div ref={messagesEndRef} />
      </div>
    </div>

    {/* Reading marker — appears only when the user has scrolled away from the
       latest message. Editorial styling: amber pill with serif label, breath
       animation matches the Reading Beat so the chat surface feels coherent. */}
    {showJumpMarker && (
      <button
        type="button"
        onClick={jumpToLatest}
        aria-label="Jump to latest message"
        className={cn(
          'group absolute bottom-4 right-5 z-10 inline-flex items-center gap-1.5',
          'rounded-full border border-amber-200/80 bg-white/85 px-3 py-1.5',
          'text-xs font-medium text-amber-800 shadow-[0_4px_14px_-4px_rgba(217,119,6,0.35)]',
          'backdrop-blur-md transition-all duration-200',
          'hover:border-amber-300 hover:bg-white hover:text-amber-900 hover:shadow-[0_6px_18px_-4px_rgba(217,119,6,0.45)]',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        )}
        style={{ animation: 'reading-bubble-in 240ms ease-out both' }}
      >
        <span className="font-serif italic tracking-tight">Jump to latest</span>
        <ArrowDown
          size={13}
          weight="bold"
          className="transition-transform duration-200 group-hover:translate-y-0.5"
        />
      </button>
    )}
    </div>
  );
});
