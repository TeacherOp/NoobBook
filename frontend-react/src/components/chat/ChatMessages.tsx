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
import { Ghost, FileText, Copy, Check, DownloadSimple } from '@phosphor-icons/react';
import type { Message } from '../../lib/api/chats';
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
import { createLogger } from '@/lib/logger';

const log = createLogger('chat-messages');

interface ChatMessagesProps {
  messages: Message[];
  sending: boolean;
  projectId: string;
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
 * Educational Note: Right-aligned bubble style for user messages
 */
const UserMessage: React.FC<{ content: string }> = ({ content }) => (
  <div className="flex justify-end w-full">
    <div className="max-w-[80%] min-w-0">
      <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2 min-w-0">
        <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
      </div>
    </div>
  </div>
);

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
    // Remove citation markers for cleaner copied text
    const cleanContent = content.replace(/\[\[cite:[^\]]+\]\]/g, '');

    try {
      await navigator.clipboard.writeText(cleanContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS or restricted contexts (e.g. iframe, older browsers)
      try {
        const textarea = document.createElement('textarea');
        textarea.value = cleanContent;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (fallbackErr) {
        log.error({ err: fallbackErr }, 'failed to copy text');
      }
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

const AIMessage: React.FC<AIMessageProps> = ({ content, projectId }) => {
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
  }), [projectId]);

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
 * Loading Indicator
 * Educational Note: Shows when AI is processing/thinking
 */
const LoadingIndicator: React.FC = () => (
  <div className="flex justify-start">
    <div className="max-w-[85%] flex gap-3">
      <div className="flex-shrink-0 mt-1">
        <Ghost size={28} weight="bold" className="text-primary" />
      </div>
      <div className="bg-muted/50 rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-xs font-medium text-muted-foreground mb-2">NoobBook</p>
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-primary/60 animate-[bounce_1.4s_ease-in-out_infinite]" />
          <span className="h-2 w-2 rounded-full bg-primary/60 animate-[bounce_1.4s_ease-in-out_0.2s_infinite]" />
          <span className="h-2 w-2 rounded-full bg-primary/60 animate-[bounce_1.4s_ease-in-out_0.4s_infinite]" />
        </div>
      </div>
    </div>
  </div>
);

/**
 * ChatMessages Component - Memoized to prevent re-renders on parent state changes
 * Educational Note: Without React.memo, every keystroke in ChatInput would
 * re-render this entire component (expensive markdown parsing). Memoization
 * ensures it only re-renders when messages, sending, or projectId actually change.
 */
export const ChatMessages: React.FC<ChatMessagesProps> = React.memo(({ messages, sending, projectId }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Track if user has manually scrolled away from bottom
  const userScrolledAwayRef = useRef(false);

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
  }, [messages, sending]);

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
    } else if (distanceFromBottom < 50) {
      userScrolledAwayRef.current = false;
    }
  };

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 min-h-0 min-w-0 w-full overflow-y-auto overflow-x-hidden bg-white"
    >
      <div className="pt-6 pb-2 px-6 space-y-4 w-full">
        {messages.map((msg) => (
          <div key={msg.id}>
            {msg.role === 'user' ? (
              <UserMessage content={msg.content} />
            ) : (
              <AIMessage
                content={msg.content}
                projectId={projectId}
              />
            )}
            {msg.error && (
              <p className="text-xs text-destructive text-center mt-1">
                This message had an error
              </p>
            )}
          </div>
        ))}

        {/* Show loading indicator when sending */}
        {sending && <LoadingIndicator />}

        {/* Invisible element to scroll to */}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
});
