/**
 * ChatMessagesSkeleton — alternating user / AI bubble placeholders
 * shown while a chat's message history is being fetched.
 *
 * Used in two places:
 *   1. ChatPanel project-mount loading branch (was a hand-rolled
 *      inline skeleton — extracted here so the two surfaces stay in
 *      lockstep).
 *   2. ChatPanel chat-switch path — sized by the sidebar's cached
 *      `message_count` so a 2-message chat shows 2 placeholders and
 *      a 20-message chat shows the capped 6.
 *
 * Why the cap: the panel scrolls; the user never sees more than a
 * handful at once. Rendering 50 placeholders for a 50-message chat
 * is just animated noise and inflates the initial paint cost for no
 * UX benefit.
 *
 * `aria-busy="true"` on the wrapper so screen readers announce
 * "loading" instead of reading the empty bubble divs aloud.
 */
import React from 'react';
import { Skeleton } from '../ui/skeleton';

const MAX_BUBBLES = 6;
const DEFAULT_BUBBLES = 4;

interface ChatMessagesSkeletonProps {
  /** Expected message count for the chat being loaded. Capped at
   * MAX_BUBBLES. Defaults to DEFAULT_BUBBLES when omitted or
   * non-positive (e.g. a brand-new chat whose count is unknown). */
  count?: number;
}

export const ChatMessagesSkeleton: React.FC<ChatMessagesSkeletonProps> = ({
  count,
}) => {
  // Brand-new chats with count=0 render nothing — the caller's empty
  // state takes over once the fetch lands.
  if (count === 0) return null;

  const bubbleCount = Math.min(
    MAX_BUBBLES,
    !count || count < 0 ? DEFAULT_BUBBLES : count,
  );

  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      {Array.from({ length: bubbleCount }, (_, i) => {
        // Alternate user (right, single bubble) / AI (left, avatar +
        // 2–3 text rows) — matches the rhythm of an actual chat
        // transcript so the placeholder reads as "messages incoming"
        // not "panel half-broken".
        const isUser = i % 2 === 0;
        // Deterministic width variation so the skeleton doesn't look
        // like a metronome. The (7 * i) % 30 nudge keeps consecutive
        // bubbles visibly different widths without random churn on
        // re-render.
        const widthPct = 55 + ((i * 7) % 30);
        return isUser ? (
          <UserBubble key={i} widthPct={widthPct} />
        ) : (
          <AIBubble key={i} widthPct={widthPct} />
        );
      })}
    </div>
  );
};

const UserBubble: React.FC<{ widthPct: number }> = ({ widthPct }) => (
  <div className="flex justify-end">
    <Skeleton
      className="h-10 rounded-2xl"
      style={{ width: `${widthPct}%` }}
    />
  </div>
);

const AIBubble: React.FC<{ widthPct: number }> = ({ widthPct }) => (
  <div className="flex justify-start gap-3">
    <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
    <div className="space-y-2 flex-1" style={{ maxWidth: `${widthPct}%` }}>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  </div>
);
