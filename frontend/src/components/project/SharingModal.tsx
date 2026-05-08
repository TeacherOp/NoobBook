import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import {
  CheckCircle,
  Clock,
  Copy,
  Globe,
  LockKey,
  Share,
  Sparkle,
  Trash,
  X,
} from '@phosphor-icons/react';
import { useToast } from '../ui/use-toast';
import { ToastContainer } from '../ui/toast';
import {
  sharesAPI,
  type InvitableUser,
  type ProjectShare,
  type ShareExpiry,
  type ShareMode,
} from '@/lib/api/shares';
import { upsertOne, removeOne } from '@/lib/resourceState';
import { copyToClipboard } from '@/lib/clipboard';
import { createLogger } from '@/lib/logger';

const log = createLogger('sharing-modal');

interface SharingModalProps {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  projectId: string;
  projectName: string;
}

/**
 * SharingModal
 *
 * Editorial / library aesthetic — warm cream background, fine rules
 * between sections, generous spacing. Intentional restraint: no flashy
 * motion, no jewel tones. The most colorful element is a thin amber
 * line under the active mode pill.
 *
 * Two regions:
 *   • Top — "Create new link" form with mode + (optional) emails + expiry.
 *   • Bottom — list of existing links with copy / revoke affordances.
 */
export const SharingModal: React.FC<SharingModalProps> = ({
  open,
  onOpenChange,
  projectId,
  projectName,
}) => {
  const { toasts, dismissToast, success, error, errorWithLogs } = useToast();

  // ── List state ───────────────────────────────────────────────────
  const [shares, setShares] = useState<ProjectShare[]>([]);
  const [listLoading, setListLoading] = useState(true);

  // ── Create form state ────────────────────────────────────────────
  const [mode, setMode] = useState<ShareMode>('public');
  const [emailDraft, setEmailDraft] = useState('');
  const [emails, setEmails] = useState<string[]>([]);
  const [expiry, setExpiry] = useState<ShareExpiry>(7);
  const [creating, setCreating] = useState(false);

  // ── Per-row state ────────────────────────────────────────────────
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // ── User search (autocomplete for invited mode) ──────────────────
  const [searchResults, setSearchResults] = useState<InvitableUser[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const resetForm = useCallback(() => {
    setMode('public');
    setEmailDraft('');
    setEmails([]);
    setExpiry(7);
  }, []);

  const fetchShares = useCallback(async () => {
    try {
      setListLoading(true);
      const res = await sharesAPI.list(projectId);
      setShares(res.data.shares || []);
    } catch (err) {
      log.error({ err }, 'failed to load shares');
      errorWithLogs('Failed to load shares');
    } finally {
      setListLoading(false);
    }
  }, [projectId, errorWithLogs]);

  useEffect(() => {
    if (!open) return;
    fetchShares();
  }, [open, fetchShares]);

  useEffect(() => {
    // Don't strand draft text when the modal closes.
    if (!open) {
      setEmailDraft('');
      setCopiedId(null);
      setSearchResults([]);
      setSearchOpen(false);
    }
  }, [open]);

  // Debounced user-search as the owner types into the chip input.
  // 200ms feels instant without flooding the backend on every keystroke.
  useEffect(() => {
    if (mode !== 'invited') return;
    const trimmed = emailDraft.trim();
    if (trimmed.length < 1) {
      setSearchResults([]);
      setSearchOpen(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const res = await sharesAPI.searchUsers(projectId, trimmed);
        if (cancelled) return;
        // Hide users already in the chip list — no point re-suggesting.
        const already = new Set(emails.map((e) => e.toLowerCase()));
        const filtered = (res.data.users || []).filter(
          (u) => u.email && !already.has(u.email.toLowerCase()),
        );
        setSearchResults(filtered);
        setSearchOpen(filtered.length > 0);
        setHighlightedIndex(0);
      } catch (err) {
        if (!cancelled) {
          log.warn({ err }, 'user search failed');
          setSearchResults([]);
          setSearchOpen(false);
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [emailDraft, mode, projectId, emails]);

  const addEmail = (raw: string) => {
    const cleaned = raw.trim().toLowerCase();
    if (!cleaned) return;
    if (!cleaned.includes('@') || !cleaned.includes('.')) {
      error('That doesn’t look like an email');
      return;
    }
    if (emails.includes(cleaned)) return;
    setEmails((prev) => [...prev, cleaned]);
    setEmailDraft('');
  };

  const handleEmailKey = (e: KeyboardEvent<HTMLInputElement>) => {
    const hasResults = searchOpen && searchResults.length > 0;

    if (e.key === 'ArrowDown' && hasResults) {
      e.preventDefault();
      setHighlightedIndex((i) => (i + 1) % searchResults.length);
      return;
    }
    if (e.key === 'ArrowUp' && hasResults) {
      e.preventDefault();
      setHighlightedIndex((i) => (i - 1 + searchResults.length) % searchResults.length);
      return;
    }
    if (e.key === 'Escape' && searchOpen) {
      e.preventDefault();
      setSearchOpen(false);
      return;
    }
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      // Prefer the highlighted suggestion if any, else fall back to the
      // raw draft so the owner can still invite an email that doesn't
      // appear in suggestions yet (e.g. because of an indexing delay).
      if (hasResults) {
        const picked = searchResults[highlightedIndex];
        if (picked?.email) {
          addEmail(picked.email);
          return;
        }
      }
      addEmail(emailDraft);
    } else if (e.key === 'Backspace' && !emailDraft && emails.length > 0) {
      setEmails((prev) => prev.slice(0, -1));
    }
  };

  const removeEmail = (e: string) => {
    setEmails((prev) => prev.filter((x) => x !== e));
  };

  const canSubmit = useMemo(() => {
    if (creating) return false;
    if (mode === 'invited' && emails.length === 0) return false;
    return true;
  }, [creating, mode, emails]);

  const handleCreate = async () => {
    if (!canSubmit) return;
    try {
      setCreating(true);
      const res = await sharesAPI.create(projectId, {
        mode,
        invited_emails: mode === 'invited' ? emails : undefined,
        expires_in_days: expiry,
      });
      const created = res.data.share;
      setShares((prev) => upsertOne(prev, created, { prepend: true }));
      success('Link created — use the copy button to share it');
      resetForm();
    } catch (err) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
      log.error({ err }, 'failed to create share');
      error(msg || 'Failed to create share link');
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async (share: ProjectShare, selectFallback: () => void) => {
    // copyToClipboard handles the modern Clipboard API + the legacy
    // execCommand fallback for non-HTTPS / unfocused contexts where
    // navigator.clipboard.writeText throws (the original failure mode here).
    // When BOTH paths fail (some browsers block execCommand inside Radix
    // portals, Safari iOS, strict Firefox), we surface the row's URL input
    // pre-selected so the user can hit Cmd/Ctrl-C immediately.
    const ok = await copyToClipboard(share.url);
    if (ok) {
      setCopiedId(share.id);
      success('Link copied');
      setTimeout(() => setCopiedId((id) => (id === share.id ? null : id)), 1600);
    } else {
      selectFallback();
      error("Couldn't auto-copy — URL is selected, press Cmd/Ctrl-C.");
    }
  };

  const handleRevoke = async (share: ProjectShare) => {
    const confirmed = window.confirm(
      `Revoke this share? Anyone using the link will lose access immediately.`,
    );
    if (!confirmed) return;
    const previous = shares;
    setShares((prev) => removeOne(prev, share.id));
    try {
      await sharesAPI.revoke(projectId, share.id);
      success('Share revoked');
    } catch (err) {
      log.error({ err }, 'failed to revoke share');
      error('Failed to revoke. Restored.');
      setShares(previous);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[540px] max-h-[90vh] p-0 overflow-hidden flex flex-col">
        <div className="px-7 pt-6 pb-4 border-b flex-shrink-0">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-semibold pr-8">
              <Share size={18} className="text-primary flex-shrink-0" />
              <span className="truncate">Share &ldquo;{projectName}&rdquo;</span>
            </DialogTitle>
            <DialogDescription className="text-xs leading-relaxed text-muted-foreground mt-1">
              Anyone with the link gets <strong>read-only</strong> access to this project&apos;s chats.
              Sources, memory, API keys, and brand stay with you.
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="flex-1 overflow-y-auto">
        {/* ── CREATE ─────────────────────────────────────────── */}
        <div className="px-7 py-5 space-y-4">
          <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            New link
          </div>

          {/* Mode pills */}
          <div className="flex items-center gap-2">
            {(['public', 'invited'] as const).map((m) => {
              const isActive = mode === m;
              return (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={[
                    'group relative px-3.5 py-1.5 text-xs rounded-full border transition-colors',
                    isActive
                      ? 'border-primary/40 bg-primary/5 text-foreground'
                      : 'border-border/60 bg-background text-muted-foreground hover:text-foreground',
                  ].join(' ')}
                  aria-pressed={isActive}
                >
                  <span className="inline-flex items-center gap-1.5">
                    {m === 'public' ? <Globe size={13} /> : <LockKey size={13} />}
                    {m === 'public' ? 'Anyone with link' : 'Specific people'}
                  </span>
                  {isActive && (
                    <span
                      aria-hidden
                      className="absolute left-3.5 right-3.5 -bottom-px h-px bg-primary/60"
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* Invited emails — chip-style input with type-ahead dropdown */}
          {mode === 'invited' && (
            <div className="space-y-2">
              <div className="relative">
                <div className="flex flex-wrap items-center gap-1.5 px-2 py-1.5 rounded-md border border-border/70 bg-background min-h-9">
                  {emails.map((e) => (
                    <span
                      key={e}
                      className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full text-[11px] font-medium bg-muted/70 border border-border/50"
                    >
                      {e}
                      <button
                        onClick={() => removeEmail(e)}
                        className="rounded-full hover:bg-stone-200/70 p-0.5"
                        aria-label={`Remove ${e}`}
                      >
                        <X size={10} weight="bold" />
                      </button>
                    </span>
                  ))}
                  <Input
                    value={emailDraft}
                    onChange={(ev) => setEmailDraft(ev.target.value)}
                    onKeyDown={handleEmailKey}
                    onFocus={() => {
                      if (searchResults.length > 0) setSearchOpen(true);
                    }}
                    // Delay close so a click on a dropdown row registers
                    // before blur kills the panel.
                    onBlur={() => {
                      setTimeout(() => setSearchOpen(false), 120);
                      if (emailDraft) addEmail(emailDraft);
                    }}
                    placeholder={emails.length ? '' : 'Search by email or paste a list'}
                    className="flex-1 min-w-[160px] h-7 px-1 border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                    aria-autocomplete="list"
                    aria-expanded={searchOpen}
                  />
                </div>

                {searchOpen && searchResults.length > 0 && (
                  <div
                    role="listbox"
                    className="absolute left-0 right-0 top-[calc(100%+4px)] z-10 max-h-[200px] overflow-y-auto rounded-md border border-border/70 bg-popover shadow-md"
                  >
                    {searchResults.map((u, idx) => {
                      const isHighlighted = idx === highlightedIndex;
                      return (
                        <button
                          key={u.id}
                          role="option"
                          aria-selected={isHighlighted}
                          // onMouseDown fires before the input's blur, so the
                          // selection completes even though blur is racing it.
                          onMouseDown={(ev) => {
                            ev.preventDefault();
                            addEmail(u.email);
                            setSearchOpen(false);
                          }}
                          onMouseEnter={() => setHighlightedIndex(idx)}
                          className={[
                            'w-full text-left px-3 py-1.5 text-xs transition-colors flex items-center justify-between gap-3',
                            isHighlighted
                              ? 'bg-primary/8 text-foreground'
                              : 'text-muted-foreground hover:bg-muted/50',
                          ].join(' ')}
                        >
                          <span className="truncate">{u.email}</span>
                          <span className="text-[10px] uppercase tracking-wide text-muted-foreground/70 flex-shrink-0">
                            User
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {searchOpen && !searching && searchResults.length === 0 && emailDraft.trim() && (
                  <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-10 rounded-md border border-border/70 bg-popover shadow-md px-3 py-2 text-[11px] text-muted-foreground">
                    No matching users — press Enter to invite anyway.
                  </div>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Invitees must have a NoobBook account with the matching email.
              </p>
            </div>
          )}

          {/* Expiry pills */}
          <div className="space-y-1.5">
            <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
              Expires
            </div>
            <div className="flex items-center gap-2">
              {([7, 30, null] as const).map((opt) => {
                const isActive = expiry === opt;
                return (
                  <button
                    key={String(opt)}
                    onClick={() => setExpiry(opt)}
                    className={[
                      'px-3 py-1 rounded-full text-xs border transition-colors',
                      isActive
                        ? 'border-primary/40 bg-primary/5 text-foreground'
                        : 'border-border/60 bg-background text-muted-foreground hover:text-foreground',
                    ].join(' ')}
                  >
                    {opt === 7 ? '7 days' : opt === 30 ? '30 days' : 'Never'}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-1">
            <Button
              onClick={handleCreate}
              disabled={!canSubmit}
              className="w-full gap-2"
            >
              <Sparkle size={14} weight="fill" />
              {creating ? 'Creating link…' : 'Create link'}
            </Button>
          </div>
        </div>

        <div className="h-px bg-border/70" />

        {/* ── ACTIVE LINKS ──────────────────────────────────── */}
        <div className="px-7 py-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
              Active links
            </div>
            {!listLoading && (
              <span className="text-[11px] text-muted-foreground">
                {shares.filter((s) => s.is_active).length} active
                {shares.filter((s) => !s.is_active).length
                  ? ` · ${shares.filter((s) => !s.is_active).length} inactive`
                  : ''}
              </span>
            )}
          </div>

          {listLoading ? (
            <div className="space-y-2.5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-[58px] rounded-lg border border-border/60 bg-muted/30 animate-pulse"
                />
              ))}
            </div>
          ) : shares.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="space-y-2">
              {shares.map((share, idx) => (
                <ShareRow
                  key={share.id}
                  share={share}
                  copied={copiedId === share.id}
                  onCopy={handleCopy}
                  onRevoke={handleRevoke}
                  staggerMs={idx * 30}
                />
              ))}
            </div>
          )}
        </div>
        </div>

        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </DialogContent>
    </Dialog>
  );
};

// ──────────────────────────────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────────────────────────────

const EmptyState: React.FC = () => (
  <div className="flex flex-col items-center justify-center py-8 px-6 text-center rounded-lg border border-dashed border-border/70">
    <div className="text-stone-400 mb-2.5">
      <Sparkle size={20} weight="duotone" />
    </div>
    <p className="text-sm font-medium text-foreground">No share links yet</p>
    <p className="text-xs text-muted-foreground mt-1 max-w-[280px] leading-relaxed">
      Create one to give read-only access to this project&apos;s chats.
    </p>
  </div>
);

interface ShareRowProps {
  share: ProjectShare;
  copied: boolean;
  onCopy: (s: ProjectShare, selectFallback: () => void) => void;
  onRevoke: (s: ProjectShare) => void;
  staggerMs: number;
}

const ShareRow: React.FC<ShareRowProps> = ({ share, copied, onCopy, onRevoke, staggerMs }) => {
  const inactive = !share.is_active;
  const inactiveLabel = share.revoked_at ? 'Revoked' : 'Expired';
  const expiryLabel = formatExpiry(share);

  // Per-row input ref — surfaces the full URL as selectable DOM text so
  // users can manually copy (Cmd/Ctrl-C) when the Clipboard API path fails.
  // The handler also auto-selects after a failed Copy click.
  const urlInputRef = useRef<HTMLInputElement | null>(null);
  // Memoised so the input doesn't see a fresh handler on every parent
  // re-render. The ref is stable, so the callback has no dependencies.
  const selectUrl = useCallback(() => {
    const el = urlInputRef.current;
    if (!el) return;
    el.focus();
    // setSelectionRange is the cross-platform-safe variant; .select() flakes
    // on some mobile browsers when the input has just received focus.
    el.setSelectionRange(0, el.value.length);
  }, []);

  return (
    <div
      style={{ animation: `share-row-in 320ms ${staggerMs}ms both ease-out` }}
      className={[
        'group relative rounded-lg border bg-card px-3 py-2.5 transition-colors',
        inactive
          ? 'border-border/40 opacity-60 hover:opacity-80'
          : 'border-border/70 hover:border-primary/30',
      ].join(' ')}
    >
      <style>{shareRowKeyframes}</style>
      <div className="flex items-center gap-3">
        {/* Mode pill */}
        <span
          className={[
            'inline-flex items-center justify-center h-7 w-7 rounded-md flex-shrink-0',
            share.mode === 'public'
              ? 'bg-primary/10 text-primary'
              : 'bg-stone-200/70 text-stone-700 dark:bg-stone-800/70 dark:text-stone-300',
          ].join(' ')}
          title={share.mode === 'public' ? 'Anyone with the link' : 'Specific people'}
        >
          {share.mode === 'public' ? (
            <Globe size={14} weight="bold" />
          ) : (
            <LockKey size={14} weight="bold" />
          )}
        </span>

        {/* URL + metadata. The URL is rendered as a read-only <input> (not a
            <span>) so users can manually triple-click + copy on browsers
            where the Clipboard API and its execCommand fallback both fail
            (Safari iOS, strict Firefox, sandboxed iframes). The value is the
            full URL with scheme — the input scrolls horizontally if needed,
            but selection always covers the entire string. */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <input
              ref={urlInputRef}
              readOnly
              value={share.url}
              onClick={selectUrl}
              onFocus={selectUrl}
              title={share.url}
              // Unique per row so screen readers can distinguish multiple
              // share inputs in the list — generic "Share link URL" alone
              // produced identical accessible names for every row.
              aria-label={`Share link URL: ${share.url}`}
              // overflow-x-auto (NOT `truncate`) so the input scrolls
              // horizontally for long URLs. `truncate` adds overflow:hidden
              // which silently clips the text inside the input — selection
              // still copies the full value, but a user clicking just to
              // visually inspect the URL would only ever see the prefix.
              className="flex-1 min-w-0 overflow-x-auto font-mono text-[11px] text-muted-foreground bg-transparent border-0 outline-none p-0 m-0 h-auto leading-normal focus-visible:ring-0 focus-visible:ring-offset-0 focus:text-foreground cursor-text"
            />
            {inactive && (
              <span className="flex-shrink-0 px-1.5 py-px rounded text-[10px] font-medium uppercase tracking-wide bg-stone-200/70 text-stone-700 dark:bg-stone-800/70 dark:text-stone-300">
                {inactiveLabel}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Clock size={11} />
              {expiryLabel}
            </span>
            {share.mode === 'invited' && share.invited_emails.length > 0 && (
              <>
                <span aria-hidden>·</span>
                <span
                  className="truncate"
                  title={share.invited_emails.join(', ')}
                >
                  {share.invited_emails.length === 1
                    ? share.invited_emails[0]
                    : `${share.invited_emails.length} people`}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <Button
            variant={copied ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => onCopy(share, selectUrl)}
            disabled={inactive}
            className="h-7 px-2.5 gap-1.5 text-xs"
            aria-label="Copy link"
          >
            {copied ? (
              <>
                <CheckCircle size={13} weight="fill" className="text-primary" />
                Copied
              </>
            ) : (
              <>
                <Copy size={13} />
                Copy
              </>
            )}
          </Button>
          {!inactive && (
            <TooltipProvider delayDuration={300}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onRevoke(share)}
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    aria-label="Revoke link"
                  >
                    <Trash size={14} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                  Revoke
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Formatting helpers
// ──────────────────────────────────────────────────────────────────

const shareRowKeyframes = `
@keyframes share-row-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}
`;

function formatExpiry(share: ProjectShare): string {
  if (share.revoked_at) return 'Revoked';
  if (!share.expires_at) return 'Never expires';
  const ms = new Date(share.expires_at).getTime() - Date.now();
  if (ms <= 0) return 'Expired';
  const days = Math.round(ms / (24 * 60 * 60 * 1000));
  if (days <= 0) {
    const hours = Math.max(1, Math.round(ms / (60 * 60 * 1000)));
    return `Expires in ${hours}h`;
  }
  if (days === 1) return 'Expires tomorrow';
  if (days < 30) return `Expires in ${days}d`;
  const date = new Date(share.expires_at);
  return `Expires ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
}

