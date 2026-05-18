/**
 * ChatPanel Component
 * Educational Note: Main orchestrator for the chat interface.
 * Composes smaller components (ChatHeader, ChatMessages, ChatInput, etc.)
 * and manages chat state and API interactions.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Sparkle } from '@phosphor-icons/react';
import axios from 'axios';
import { Skeleton } from '../ui/skeleton';
import { chatsAPI } from '@/lib/api/chats';
import type { Chat, ChatMetadata, ChatSyncPayload, StudioSignal } from '@/lib/api/chats';
import type { CostTracking } from '@/lib/api/projects';
import { usersAPI, type UserUsage } from '@/lib/api/settings';
import { sourcesAPI, type Source } from '@/lib/api/sources';
import { ToastContainer } from '../ui/toast';
import { useToast } from '../ui/use-toast';
import { useVoiceRecording } from '../hooks/useVoiceRecording';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { ChatList } from './ChatList';
import { ChatEmptyState } from './ChatEmptyState';
import { RawMessageView } from './RawMessageView';
import { exportChatAsPdf } from '@/lib/exportChatPdf';
import { createLogger } from '@/lib/logger';
import { API_BASE_URL } from '@/lib/api/client';

const log = createLogger('chat-panel');

interface ChatPanelProps {
  projectId: string;
  projectName: string;
  sourcesVersion?: number;
  onCostsChange?: () => void; // Called after message sent to trigger cost refresh
  onSignalsChange?: (signals: StudioSignal[]) => void; // Called when studio signals change
  selectedSourceIds: string[]; // Per-chat source selection from parent
  onActiveChatChange: (chatId: string | null, selectedSourceIds: string[]) => void; // Notify parent of chat change
  sendingChatIds: Set<string>; // All chats currently processing (owned by parent)
  onAddSendingChat: (chatId: string, chatName?: string) => void;
  onRemoveSendingChat: (chatId: string) => void;
  openChatId?: string | null; // When set, ChatPanel switches to this chat
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  projectId,
  projectName,
  sourcesVersion,
  onCostsChange,
  onSignalsChange,
  selectedSourceIds,
  onActiveChatChange,
  sendingChatIds,
  onAddSendingChat,
  onRemoveSendingChat,
  openChatId,
}) => {
  const { toasts, dismissToast, success, error, errorWithLogs } = useToast();

  // Chat state
  const [message, setMessage] = useState('');
  // Inline image attachments (paste, drag-and-drop, or image-button picker).
  // Cleared on send so the next message starts clean. Lives at panel level
  // — not ChatInput — so optimistic-render / chat-switch logic can read it.
  const [attachments, setAttachments] = useState<File[]>([]);
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [showChatList, setShowChatList] = useState(false);
  const [allChats, setAllChats] = useState<ChatMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  // Derive sending state for current chat from parent-owned Set
  const sending = activeChat ? sendingChatIds.has(activeChat.id) : false;
  const [exportingChat, setExportingChat] = useState(false);
  const [rawMode, setRawMode] = useState(false);
  const [streamingAssistantContent, setStreamingAssistantContent] = useState('');
  // Latest tool_progress message — shown inside the ReadingIndicator
  // while the assistant is silent (e.g. FreshdeskAgent iterating). Cleared
  // when assistant text starts streaming or when the run finishes/errors.
  const [toolProgress, setToolProgress] = useState<string>('');
  const [titleSyncPollKey, setTitleSyncPollKey] = useState(0);
  // AbortController for cancelling in-flight chat requests
  const abortControllerRef = useRef<AbortController | null>(null);
  // Synchronous lock that prevents duplicate handleSend calls slipping past
  // the React-state `sending` guard. setSendingChatIds is async — a rapid
  // double-click (or programmatic re-submit from a keyboard handler firing
  // alongside a click handler) can have both invocations read `sending=false`
  // before the first setState commits. A ref toggled inside handleSend
  // closes that window because ref writes are synchronous.
  // Without this, prod logs show two FreshdeskAgent workers spawning at the
  // same second for the same chat (97c88b5c + b71721c2 at 07:27:27).
  const sendingLockRef = useRef(false);
  const canonicalUserMessageReceivedRef = useRef(false);
  const assistantDeltaReceivedRef = useRef(false);
  const pendingTitleSyncRef = useRef<{ chatId: string; hasSeenNamingTask: boolean } | null>(null);
  // Mirrors activeChat?.id so async callbacks (recoverChatFromServer) can
  // check "is the user still on the originating chat?" *synchronously*
  // without going through a setState updater — React 18's automatic
  // batching means functional-updater side effects don't run before the
  // line that reads them, which broke the previous guard pattern.
  const activeChatIdRef = useRef<string | null>(null);
  // Mirrors `activeChat?.messages?.length`. Read by `recoverChatFromServer`
  // to detect when the server view is behind local optimistic state — done
  // via a ref (rather than peeking inside a `setActiveChat` updater) so
  // the read is genuinely side-effect-free and Strict Mode's double-invoke
  // of state updaters can't corrupt the snapshot.
  const activeChatMessageCountRef = useRef(0);

  // Sources state for header display
  const [sources, setSources] = useState<Source[]>([]);

  // Per-chat cost tracking (shown in ChatHeader)
  const [chatCosts, setChatCosts] = useState<CostTracking | null>(null);

  // User spending limit usage (compact progress bar in ChatHeader)
  const [userUsage, setUserUsage] = useState<UserUsage | null>(null);

  // Active sources count derived from per-chat selection
  const activeSources = selectedSourceIds.length;

  // Voice recording hook
  const {
    isRecording,
    partialTranscript,
    transcriptionConfigured,
    startRecording,
    stopRecording,
  } = useVoiceRecording({
    onError: error,
    onTranscriptCommit: useCallback((text: string) => {
      // Append committed text to message
      setMessage((prev) => {
        if (prev && !prev.endsWith(' ')) {
          return prev + ' ' + text;
        }
        return prev + text;
      });
    }, []),
  });

  /**
   * Load sources for the project (for header display)
   */
  const loadSources = async () => {
    try {
      const data = await sourcesAPI.listSources(projectId);
      setSources(data);
    } catch (err) {
      log.error({ err }, 'failed to load sources');
    }
  };

  /**
   * Merge a server-fetched chat into the local optimistic one, keeping any
   * local messages the server doesn't yet know about.
   *
   * Why: the FIRST message of a fresh chat exposes a tight race between
   * the server emitting `assistant_done` and committing `add_assistant_message`
   * to the DB. If a recovery / refresh path fetches in that microsecond
   * window, the server view has the user message but not the assistant
   * reply — a flat `setActiveChat(chat)` would wipe the assistant text we
   * just streamed in via `appendAssistantMessage`, and the user only sees
   * the reply after a manual refresh. Merging keeps server messages as
   * canonical (correct ids / timestamps) and appends any local-only
   * messages (temp-* user messages mid-stream, optimistically-appended
   * assistant messages that landed ahead of a slow recovery fetch).
   */
  const mergeChatPreservingLocal = useCallback(
    (local: Chat | null, server: Chat): Chat => {
      if (!local || local.id !== server.id) return server;
      const serverIds = new Set(
        server.messages.map((m) => m.id).filter((id): id is string => Boolean(id)),
      );
      const localOnly = local.messages.filter((m) => m.id && !serverIds.has(m.id));
      if (localOnly.length === 0) return server;
      if (import.meta.env.DEV) {
        log.info(
          { chatId: server.id, localOnlyIds: localOnly.map((m) => m.id) },
          'mergeChatPreservingLocal: keeping local-only messages',
        );
      }
      return {
        ...server,
        messages: [...server.messages, ...localOnly],
      };
    },
    [],
  );

  /**
   * Load full chat data including all messages.
   *
   * Guarded against the user being mid-send on this chat: a flat replace
   * from the server would wipe the optimistic temp user message and the
   * just-streamed assistant text. When `sendingLockRef` is held for this
   * chat we merge instead of replacing.
   */
  const loadFullChat = async (chatId: string) => {
    try {
      const chat = await chatsAPI.getChat(projectId, chatId);
      const midSend = sendingLockRef.current && activeChatIdRef.current === chatId;
      setActiveChat((prev) => {
        if (import.meta.env.DEV) {
          log.info(
            { chatId, midSend, prevMessageCount: prev?.messages?.length, serverMessageCount: chat.messages.length },
            'loadFullChat: setActiveChat',
          );
        }
        return midSend ? mergeChatPreservingLocal(prev, chat) : chat;
      });
      // Notify parent of per-chat source selection
      onActiveChatChange(chat.id, chat.selected_source_ids ?? []);
    } catch (err) {
      log.error({ err }, 'failed to load chat');
      errorWithLogs('Failed to load chat');
    }
  };

  /**
   * Load all chats for the project
   */
  const loadChats = async () => {
    try {
      setLoading(true);
      const chats = await chatsAPI.listChats(projectId);
      setAllChats(chats);

      // If we have chats and no active chat, load the first one
      if (chats.length > 0 && !activeChat) {
        await loadFullChat(chats[0].id);
      }
    } catch (err) {
      log.error({ err }, 'failed to load chats');
      errorWithLogs('Failed to load chats');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load all chats and sources when component mounts or projectId changes
   */
  useEffect(() => {
    loadChats();
    loadSources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Switch to a specific chat when parent requests it (e.g. from ActiveTasksBar "Open" button)
  useEffect(() => {
    if (openChatId && openChatId !== activeChat?.id) {
      loadFullChat(openChatId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openChatId]);

  // Refetch the active chat when something background writes to it
  // (e.g. a saved-insight refresh appending a turn). Listening for a
  // window event keeps ChatPanel decoupled from whatever fired the
  // refresh; the event detail just carries the chat_id so we can
  // skip refetches for chats the user isn't viewing.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ chatId?: string }>).detail;
      if (detail?.chatId && detail.chatId === activeChatIdRef.current) {
        loadFullChat(detail.chatId);
      }
    };
    window.addEventListener('noobbook:chat:updated', handler);
    return () => window.removeEventListener('noobbook:chat:updated', handler);
    // loadFullChat is stable for our purposes (closes over projectId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Refetch sources when sourcesVersion changes
   * Educational Note: This triggers when SourcesPanel notifies us that sources
   * have changed (toggle active, delete, processing complete, etc.)
   */
  useEffect(() => {
    if (sourcesVersion !== undefined && sourcesVersion > 0) {
      loadSources();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourcesVersion]);

  /**
   * Notify parent when studio signals change
   * Educational Note: Signals are stored in the chat and loaded/updated
   * when chat is loaded or after messages are sent.
   */
  useEffect(() => {
    if (activeChat) {
      onSignalsChange?.(activeChat.studio_signals || []);
    } else {
      onSignalsChange?.([]);
    }
  }, [activeChat, onSignalsChange]);

  // Keep the activeChatId + message-count refs in sync — read-only mirrors
  // used by async recovery paths so they can compare current chat without
  // racing with batched state updates.
  useEffect(() => {
    activeChatIdRef.current = activeChat?.id ?? null;
    activeChatMessageCountRef.current = activeChat?.messages?.length ?? 0;
  }, [activeChat?.id, activeChat?.messages?.length]);

  /**
   * Load per-chat cost/token breakdown whenever the active chat changes.
   * Refreshed again after each message via `loadChatCosts()` in the send flow.
   */
  const loadChatCosts = useCallback(async (chatId: string) => {
    try {
      const costs = await chatsAPI.getCosts(projectId, chatId);
      setChatCosts(costs);
    } catch (err) {
      log.error({ err }, 'failed to load chat costs');
    }
  }, [projectId]);

  const loadUserUsage = useCallback(async () => {
    try {
      const data = await usersAPI.getMyUsage();
      setUserUsage(data);
    } catch {
      // Silent — usage is not critical
    }
  }, []);

  const applyChatSync = useCallback((sync?: ChatSyncPayload | null): boolean => {
    if (!sync?.chat) {
      return false;
    }

    const syncedChat = sync.chat;

    setAllChats((prev) => {
      const existing = prev.find((chat) => chat.id === syncedChat.id);
      const nextChat: ChatMetadata = {
        id: syncedChat.id,
        title: syncedChat.title,
        created_at: syncedChat.created_at,
        updated_at: syncedChat.updated_at,
        message_count: syncedChat.message_count,
      };

      if (existing &&
          existing.title === nextChat.title &&
          existing.updated_at === nextChat.updated_at &&
          existing.message_count === nextChat.message_count) {
        return prev;
      }

      return [nextChat, ...prev.filter((chat) => chat.id !== syncedChat.id)];
    });

    setActiveChat((prev) => {
      if (!prev || prev.id !== syncedChat.id) {
        return prev;
      }

      return {
        ...prev,
        title: syncedChat.title,
        updated_at: syncedChat.updated_at,
        selected_source_ids: syncedChat.selected_source_ids,
        studio_signals: sync.studio_signals ?? prev.studio_signals,
      };
    });

    if (sync.chat_costs) {
      setChatCosts(sync.chat_costs);
    }

    if (sync.user_usage) {
      setUserUsage(sync.user_usage);
    }

    onCostsChange?.();
    return true;
  }, [onCostsChange]);

  /**
   * Refetch a chat's full state when SSE streaming ended without a terminal
   * event (proxy truncation, network drop, etc.). Backend has already
   * persisted whatever it produced, so we just need to surface it.
   *
   * Chat-id-aware: if the user has switched to a different chat by the
   * time the refetch returns, the activeChat replacement and source-
   * selection notification are skipped so the recovery doesn't yank
   * them back to the chat they navigated away from.
   *
   * The "still on this chat?" check is read off `activeChatIdRef` (kept
   * in sync via useEffect above) — synchronously and reliably. A prior
   * version of this helper used a side effect inside a setActiveChat
   * functional updater, which doesn't fire before the line that reads
   * it under React 18 automatic batching (Greptile flagged this on
   * PR #204). The functional updater on setActiveChat is still kept as
   * defence-in-depth against a chat switch racing in between the ref
   * check and the actual state commit.
   */
  const recoverChatFromServer = useCallback(
    async (chatId: string, errorToastMessage?: string) => {
      // Snapshot local message count from the dedicated ref. Reading it
      // here (rather than peeking inside a `setActiveChat` updater) keeps
      // the state updater pure — required for Strict Mode's intentional
      // double-invoke, and just generally idiomatic React.
      const localMessageCount =
        activeChatIdRef.current === chatId ? activeChatMessageCountRef.current : 0;

      try {
        let chat = await chatsAPI.getChat(projectId, chatId);
        // Up to 2 retries (400ms, 800ms) when the server appears behind
        // local — covers the assistant-just-streamed-but-DB-not-flushed
        // window. Three fetches total worst case.
        const RECOVERY_RETRY_DELAYS_MS = [400, 800];
        for (const delay of RECOVERY_RETRY_DELAYS_MS) {
          if (chat.messages.length >= localMessageCount) break;
          if (import.meta.env.DEV) {
            log.info(
              { chatId, serverCount: chat.messages.length, localCount: localMessageCount, delay },
              'recoverChatFromServer: server behind local, retrying',
            );
          }
          await new Promise((resolve) => setTimeout(resolve, delay));
          chat = await chatsAPI.getChat(projectId, chatId);
        }

        const stillActive = activeChatIdRef.current === chat.id;
        if (stillActive) {
          setActiveChat((prev) => {
            if (!prev || prev.id !== chat.id) return prev;
            if (import.meta.env.DEV) {
              log.info(
                { chatId, prevCount: prev.messages.length, serverCount: chat.messages.length },
                'recoverChatFromServer: setActiveChat (merge)',
              );
            }
            return mergeChatPreservingLocal(prev, chat);
          });
          onActiveChatChange(chat.id, chat.selected_source_ids ?? []);
        }
        onCostsChange?.();
        await loadUserUsage();
      } catch (recoveryErr) {
        log.error({ err: recoveryErr, chatId }, 'recovery refetch failed');
        // An explicit empty string from the caller silences the toast —
        // used by the post-`assistant_done` defence-in-depth refetch,
        // where the user already received a complete reply and a
        // "Connection dropped" banner would be a confusing false alarm.
        // `undefined` (the normal call shape) still gets the default message.
        if (errorToastMessage !== '') {
          errorWithLogs(
            errorToastMessage ||
              'Connection dropped before the response arrived. Refresh to load it.',
          );
        }
      }
    },
    [projectId, onActiveChatChange, onCostsChange, loadUserUsage, errorWithLogs, mergeChatPreservingLocal],
  );

  const reconcileChatMetadata = useCallback(async (chatId: string) => {
    try {
      const [chat] = await Promise.all([
        chatsAPI.getChat(projectId, chatId),
        loadChatCosts(chatId),
        loadUserUsage(),
      ]);

      setAllChats((prev) => {
        const existing = prev.find((item) => item.id === chat.id);
        const nextChat: ChatMetadata = existing
          ? {
              ...existing,
              title: chat.title,
              updated_at: chat.updated_at,
              message_count: chat.messages.length,
            }
          : {
              id: chat.id,
              title: chat.title,
              created_at: chat.created_at,
              updated_at: chat.updated_at,
              message_count: chat.messages.length,
            };

        return [nextChat, ...prev.filter((item) => item.id !== chat.id)];
      });

      setActiveChat((prev) => {
        if (!prev || prev.id !== chat.id) {
          return prev;
        }

        return {
          ...prev,
          title: chat.title,
          updated_at: chat.updated_at,
          selected_source_ids: chat.selected_source_ids,
          studio_signals: chat.studio_signals || prev.studio_signals,
        };
      });
    } catch (err) {
      log.error({ err, chatId }, 'failed to reconcile chat metadata');
    }
  }, [loadChatCosts, loadUserUsage, projectId]);

  useEffect(() => {
    if (activeChat?.id) {
      loadChatCosts(activeChat.id);
    } else {
      setChatCosts(null);
    }
  }, [activeChat?.id, loadChatCosts]);

  // Load user usage on mount
  useEffect(() => {
    loadUserUsage();
  }, [loadUserUsage]);

  useEffect(() => {
    if (!pendingTitleSyncRef.current) {
      return undefined;
    }

    const pending = pendingTitleSyncRef.current;
    const startedAt = Date.now();
    // Ceiling so a fast-completing name task that we never observe in
    // /active-tasks still triggers a reconcile. Haiku often returns in
    // 1-3s, so anything past 8s means either we missed the window or the
    // task failed silently — either way, pull fresh metadata.
    const MAX_WAIT_MS = 8000;
    let cancelled = false;

    const finishAndReconcile = async () => {
      pendingTitleSyncRef.current = null;
      await reconcileChatMetadata(pending.chatId);
      if (!cancelled) {
        setTitleSyncPollKey((prev) => prev + 1);
      }
    };

    const checkForCompletedNaming = async () => {
      if (cancelled || pendingTitleSyncRef.current !== pending) {
        return;
      }

      const elapsed = Date.now() - startedAt;

      try {
        const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/active-tasks`);
        if (cancelled || pendingTitleSyncRef.current !== pending) {
          return;
        }

        const namingTask = response.data.success
          ? (response.data.tasks || []).find((task: {
              type?: string;
              target_id?: string;
              target_type?: string;
              task_type?: string;
            }) => (
              task.type === 'background' &&
              task.target_type === 'chat' &&
              task.target_id === pending.chatId &&
              task.task_type === 'chat_naming'
            ))
          : undefined;

        if (namingTask) {
          pending.hasSeenNamingTask = true;
          return;
        }

        if (pending.hasSeenNamingTask || elapsed >= MAX_WAIT_MS) {
          await finishAndReconcile();
        }
      } catch {
        if (elapsed >= MAX_WAIT_MS && !cancelled && pendingTitleSyncRef.current === pending) {
          await finishAndReconcile();
        }
      }
    };

    void checkForCompletedNaming();
    const intervalId = window.setInterval(() => {
      void checkForCompletedNaming();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [projectId, reconcileChatMetadata, titleSyncPollKey]);

  /**
   * Send a message and get AI response
   * Educational Note: We add the user message optimistically to the UI
   * before the API call, so users see their message immediately.
   */
  const handleSend = async () => {
    // Ref-based atomic guard. The React-state `sending` flag is set via
    // onAddSendingChat below but doesn't reflect until the next render —
    // a rapid second invocation in the same tick passes the `sending` check
    // and slips through. The ref is set synchronously and released in the
    // try/finally wrapper around the actual send work.
    if (sendingLockRef.current) return;
    if (!activeChat || sending) return;
    // Send-enabled if EITHER the text is non-empty OR there's at least one
    // attachment. Pure-attachment messages ("here's a screenshot, no
    // caption") are valid — Claude still answers from the image alone.
    if (!message.trim() && attachments.length === 0) return;
    sendingLockRef.current = true;

    const userMessage = message.trim();
    const messageAttachments = attachments;
    const currentChat = activeChat;
    const sendingChatId = currentChat.id;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    canonicalUserMessageReceivedRef.current = false;
    assistantDeltaReceivedRef.current = false;
    setMessage('');
    setAttachments([]);
    setRawMode(false);
    setStreamingAssistantContent('');
    setToolProgress('');
    onAddSendingChat(sendingChatId, activeChat.title);

    // Optimistic user-message render. With attachments, the content is a
    // typed-block list using local blob URLs so the screenshot appears in
    // the bubble before the network roundtrip — replaceTempWithCanonical
    // swaps in server-signed URLs once the backend persists.
    //
    // Memory management: each blob URL pins the underlying File data in
    // browser memory until URL.revokeObjectURL() runs. We track the URLs
    // created here and revoke them in three places: (a) when the canonical
    // user message arrives with server-signed URLs (the local blobs are no
    // longer rendered), (b) when the temp message is removed on send
    // failure, (c) in the finally block as a defence-in-depth catch-all.
    const optimisticBlobUrls: string[] = [];
    const optimisticContent = messageAttachments.length
      ? [
          ...messageAttachments.map((file) => {
            const blobUrl = URL.createObjectURL(file);
            optimisticBlobUrls.push(blobUrl);
            return {
              type: 'image' as const,
              url: blobUrl,
              media_type: file.type,
              filename: file.name,
            };
          }),
          { type: 'text' as const, text: userMessage },
        ]
      : userMessage;
    const revokeOptimisticBlobs = () => {
      for (const url of optimisticBlobUrls.splice(0)) {
        URL.revokeObjectURL(url);
      }
    };

    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      role: 'user' as const,
      content: optimisticContent,
      timestamp: new Date().toISOString(),
    };

    setActiveChat((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...prev.messages, tempUserMessage],
      };
    });

    const replaceTempWithCanonicalUser = (canonicalUserMessage: Chat['messages'][number]) => {
      // Some SSE producers occasionally emit a `user_message` event with a
      // missing/null payload during reconnects. Bail out instead of poisoning
      // activeChat.messages with `undefined`, which crashes the renderer
      // (`Cannot read properties of undefined (reading 'id')`).
      if (!canonicalUserMessage?.id) return;
      canonicalUserMessageReceivedRef.current = true;
      // Carry the optimistic blob URLs onto the canonical message's image
      // blocks. The server-signed URLs aren't always reachable from the
      // browser in the active session (proxy / cache / momentary RLS race),
      // and an earlier revision swapped to them on this event — making the
      // image vanish from the bubble the moment the AI started answering.
      // Local blob URLs are guaranteed-live for the page lifetime, so we
      // keep them for *this* session; on full page refresh, the persisted
      // image blocks rebuild from a fresh signed URL via the formatter.
      let mergedCanonical: Chat['messages'][number] = canonicalUserMessage;
      if (
        Array.isArray(canonicalUserMessage.content) &&
        Array.isArray(optimisticContent) &&
        optimisticBlobUrls.length > 0
      ) {
        // Build a filename → blobUrl lookup from the optimistic blocks so
        // the merge is order-independent (the server may return image blocks
        // in a different sequence than the client built them).
        const blobByFilename = new Map<string, string>();
        for (const block of optimisticContent) {
          if (
            typeof block === 'object' &&
            block.type === 'image' &&
            block.filename &&
            block.url &&
            !blobByFilename.has(block.filename)
          ) {
            blobByFilename.set(block.filename, block.url);
          }
        }
        const mergedContent = (canonicalUserMessage.content as Array<{ type: string; url?: string; filename?: string }>).map(
          (block) => {
            if (block.type === 'image' && block.filename) {
              const blobUrl = blobByFilename.get(block.filename);
              if (blobUrl) return { ...block, url: blobUrl };
            }
            return block;
          },
        );
        mergedCanonical = {
          ...canonicalUserMessage,
          content: mergedContent as Chat['messages'][number]['content'],
        };
      }
      setActiveChat((prev) => {
        if (!prev) return null;
        const nextMessages = prev.messages.map((msg) =>
          msg.id === tempUserMessage.id ? mergedCanonical : msg
        );
        const alreadyPresent = nextMessages.some((msg) => msg.id === mergedCanonical.id);
        return {
          ...prev,
          messages: alreadyPresent ? nextMessages : [...nextMessages.filter((msg) => msg.id !== tempUserMessage.id), mergedCanonical],
        };
      });
      // Intentionally NOT revoking optimisticBlobUrls here — the merged
      // canonical message is still pointing at them. They'll be released
      // when the browser tab navigates away. The small per-image
      // (≤5MB cap) memory cost is the trade-off for a working preview
      // throughout the session.
    };

    const appendAssistantMessage = (assistantMessage: Chat['messages'][number]) => {
      // Same defensive guard as replaceTempWithCanonicalUser. See note there.
      if (!assistantMessage?.id) {
        log.warn('appendAssistantMessage called with empty payload — ignoring');
        setStreamingAssistantContent('');
        return;
      }
      // Append the final message first, THEN clear streaming content in the
      // same React batch. This prevents a flash where neither the streaming
      // bubble nor the final message is visible.
      setActiveChat((prev) => {
        if (!prev) return null;
        const messagesWithoutTemp = prev.messages.filter((m) => m.id !== tempUserMessage.id);
        const alreadyAppended = messagesWithoutTemp.some((msg) => msg.id === assistantMessage.id);
        if (import.meta.env.DEV) {
          log.info(
            { chatId: prev.id, assistantId: assistantMessage.id, prevCount: prev.messages.length, alreadyAppended },
            'appendAssistantMessage: setActiveChat',
          );
        }
        if (alreadyAppended) {
          return { ...prev, messages: messagesWithoutTemp, updated_at: new Date().toISOString() };
        }
        return {
          ...prev,
          messages: [...messagesWithoutTemp, assistantMessage],
          updated_at: new Date().toISOString(),
        };
      });
      setStreamingAssistantContent('');
    };

    const applyFallbackResponse = (result: {
      user_message: Chat['messages'][number];
      assistant_message: Chat['messages'][number];
      sync?: ChatSyncPayload | null;
    }) => {
      canonicalUserMessageReceivedRef.current = true;
      setStreamingAssistantContent('');
      setActiveChat((prev) => {
        if (!prev) return null;
        const messagesWithoutTemp = prev.messages.filter((m) => m.id !== tempUserMessage.id);
        // Filter out anything missing an `id` so a malformed REST fallback
        // payload doesn't crash the renderer downstream.
        const incoming = [result.user_message, result.assistant_message].filter(
          (m): m is Chat['messages'][number] => Boolean(m?.id),
        );
        return {
          ...prev,
          messages: [...messagesWithoutTemp, ...incoming],
          updated_at: new Date().toISOString(),
        };
      });
    };

    const shouldWatchForTitleUpdate = currentChat.messages.length === 0;
    if (shouldWatchForTitleUpdate) {
      pendingTitleSyncRef.current = {
        chatId: currentChat.id,
        hasSeenNamingTask: false,
      };
      setTitleSyncPollKey((prev) => prev + 1);
    }

    let receivedTerminalSync = false;

    try {
      const streamResult = await chatsAPI.streamMessage(
        projectId,
        currentChat.id,
        userMessage,
        {
          onUserMessage: replaceTempWithCanonicalUser,
          onAssistantDelta: (delta) => {
            assistantDeltaReceivedRef.current = true;
            // Once real assistant text is flowing the tool_progress chip
            // would just clutter the UI — content takes over the bubble.
            setToolProgress('');
            setStreamingAssistantContent((prev) => prev + delta);
          },
          onToolProgress: (payload) => {
            setToolProgress(payload.message);
          },
          onAssistantDone: (payload) => {
            setToolProgress('');
            appendAssistantMessage(payload.assistant_message);
            receivedTerminalSync = applyChatSync(payload.sync);
            // Defence in depth: even after `assistant_done` and the
            // happy-path append, schedule a silent merge-refetch ~500ms
            // later. If anything in the next render cycle (a refetch
            // racing the SSE handler, a `loadFullChat` flat-replace from
            // an `openChatId` update, etc.) wiped the assistant message
            // from local state, this brings it back from the DB without
            // a visible flicker. Chat-id-aware: if the user navigated
            // away by then, `recoverChatFromServer`'s `stillActive`
            // check skips the update.
            const recoveryChatId = currentChat.id;
            setTimeout(() => {
              // Pass an explicit empty string so a transient failure on
              // this silent follow-up fetch doesn't surface a misleading
              // "Connection dropped" toast — the user already saw the
              // complete reply. recoverChatFromServer treats `""` as
              // "skip the toast".
              void recoverChatFromServer(recoveryChatId, '');
            }, 500);
          },
          onErrorEvent: (payload) => {
            setToolProgress('');
            setStreamingAssistantContent('');
            if (payload.assistant_message) {
              appendAssistantMessage(payload.assistant_message);
            }
            receivedTerminalSync = applyChatSync(payload.sync);
          },
        },
        controller.signal,
        messageAttachments,
      );

      if (streamResult.terminalEvent) {
        if (!receivedTerminalSync && streamResult.terminalSync) {
          receivedTerminalSync = applyChatSync(streamResult.terminalSync);
        }
        if (!receivedTerminalSync) {
          onCostsChange?.();
          await reconcileChatMetadata(currentChat.id);
        }
      } else {
        // Stream closed cleanly but neither `assistant_done` nor `error`
        // arrived. The most common cause is an upstream proxy (frontend
        // nginx, Coolify Traefik) FIN'ing the connection during a long
        // tool-use gap — the backend has already persisted the assistant
        // message via main_chat_service, so a refetch surfaces it without
        // re-running the model. Without this branch the UI stuck on the
        // Reading Beat until the user manually refreshed (prod logs
        // showed 407s / 523s / 658s streams driving the bug).
        log.warn(
          {
            chatId: currentChat.id,
            hadUserMessage: streamResult.hadUserMessage,
            hadAssistantDelta: streamResult.hadAssistantDelta,
          },
          'stream ended without terminal event — recovering from server',
        );
        setStreamingAssistantContent('');
        await recoverChatFromServer(currentChat.id);
      }
    } catch (err) {
      // Don't show error toast if user intentionally stopped
      const isAborted = err instanceof Error && (err.name === 'CanceledError' || err.name === 'AbortError');
      if (isAborted) {
        log.info('Chat request stopped by user');
      } else {
        const shouldFallback = !canonicalUserMessageReceivedRef.current && !assistantDeltaReceivedRef.current;
        // The REST fallback (chatsAPI.sendMessage) is text-only — it
        // can't carry image attachments. If the user attached anything,
        // skip the silent fallback and surface the error so they can
        // re-paste/re-drop and retry. Falling back would silently drop
        // the screenshot, producing a confusing answer to the visual
        // question they asked.
        const hasAttachments = messageAttachments.length > 0;

        if (shouldFallback && !hasAttachments) {
          try {
            const fallbackResult = await chatsAPI.sendMessage(projectId, currentChat.id, userMessage);
            applyFallbackResponse(fallbackResult);
            if (!applyChatSync(fallbackResult.sync)) {
              onCostsChange?.();
              await reconcileChatMetadata(currentChat.id);
            }
          } catch (fallbackError) {
            log.error({ err: fallbackError }, 'failed to send message via fallback');
            errorWithLogs('Failed to send message');
          }
        } else if (shouldFallback && hasAttachments) {
          log.warn('stream failed before user_message event with attachments — surfacing error so user can retry');
          errorWithLogs('Failed to send message — please retry.');
        } else {
          // Stream errored mid-flight after delivering partial events
          // (canonical user_message and/or assistant_delta). Re-sending
          // via the REST fallback would duplicate the user's message —
          // recover by re-fetching the chat instead. The backend's
          // exception handler in main_chat_service already persists an
          // error-marked assistant message before the SSE error event,
          // so the refetch surfaces either the partial response or a
          // recorded failure the user can retry from.
          log.warn({ err }, 'stream errored after partial events — recovering from server');
          await recoverChatFromServer(currentChat.id, 'Failed to send message');
        }
      }
      setStreamingAssistantContent('');
      if (!canonicalUserMessageReceivedRef.current) {
        setActiveChat((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            messages: prev.messages.filter((m) => m.id !== tempUserMessage.id),
          };
        });
      }
    } finally {
      onRemoveSendingChat(sendingChatId);
      abortControllerRef.current = null;
      sendingLockRef.current = false;
      // Belt-and-braces: also clear here in case onToolProgress fired
      // after onErrorEvent (out-of-order arrivals on slow networks).
      setToolProgress('');
      // Only revoke optimistic blob URLs if we never got a canonical
      // user message to attach them to (send-aborted, fallback-error,
      // user-cancelled). When the canonical did arrive, the merged
      // message is still pointing at these blob URLs — revoking here
      // would be the bug we're fixing. The browser will free them when
      // the tab navigates.
      if (!canonicalUserMessageReceivedRef.current) {
        revokeOptimisticBlobs();
      }
    }
  };

  /**
   * Stop the current in-flight chat request
   */
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreamingAssistantContent('');
  };

  /**
   * Create a new chat
   */
  const handleNewChat = async () => {
    try {
      const newChat = await chatsAPI.createChat(projectId, 'New Chat');
      setAllChats((prev) => [newChat, ...prev]);
      await loadFullChat(newChat.id);
      // Backend pre-seeds selected_source_ids with the project's DB-type
      // sources on chat create (Sno 40 / #247); loadFullChat fetches that
      // selection and notifies parents via onActiveChatChange.
      setShowChatList(false);
      success('New chat created');
    } catch (err) {
      log.error({ err }, 'failed to create chat');
      error('Failed to create chat');
    }
  };

  // Keep a ref to the latest handleNewChat so the global keydown listener
  // (mounted once) always fires the up-to-date closure instead of capturing
  // the first render's stale setters / toast helpers.
  const handleNewChatRef = useRef(handleNewChat);
  handleNewChatRef.current = handleNewChat;

  // Cmd/Ctrl+Shift+O → new chat (Claude-app parity, Sno 51 / GH #254).
  // Overrides Chrome's bookmarks-manager binding intentionally — matches
  // Claude.app's behaviour. Only mounted while ChatPanel is rendered (i.e.
  // inside a project workspace), so the shortcut is workspace-scoped.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === 'o'
      ) {
        e.preventDefault();
        e.stopPropagation();
        handleNewChatRef.current();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  /**
   * Select a chat from the list
   */
  const handleSelectChat = async (chatId: string) => {
    await loadFullChat(chatId);
    setShowChatList(false);
  };

  /**
   * Delete a chat
   */
  const handleDeleteChat = async (chatId: string) => {
    try {
      await chatsAPI.deleteChat(projectId, chatId);
      const remainingChats = allChats.filter((chat) => chat.id !== chatId);
      setAllChats(remainingChats);

      // If the deleted chat was active, clear it and reset source selection
      if (activeChat?.id === chatId) {
        setActiveChat(null);
        onActiveChatChange(null, []);

        if (remainingChats.length > 0) {
          await loadFullChat(remainingChats[0].id);
        }
      }
      success('Chat deleted');
    } catch (err) {
      log.error({ err }, 'failed to delete chat');
      error('Failed to delete chat');
    }
  };

  /**
   * Rename a chat
   */
  const handleRenameChat = async (chatId: string, newTitle: string) => {
    try {
      const updatedChat = await chatsAPI.updateChat(projectId, chatId, newTitle);
      setAllChats((prev) => prev.map((chat) => (
        chat.id === chatId
          ? {
              ...chat,
              title: updatedChat.title,
              updated_at: updatedChat.updated_at,
              message_count: updatedChat.message_count,
            }
          : chat
      )));

      // Update active chat if it was renamed
      if (activeChat?.id === chatId) {
        setActiveChat(prev => prev ? { ...prev, title: updatedChat.title } : null);
      }

      success('Chat renamed');
    } catch (err) {
      log.error({ err }, 'failed to rename chat');
      error('Failed to rename chat');
    }
  };

  /**
   * Toggle recording on/off
   */
  const handleMicClick = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  /**
   * Export the active chat as a PDF file
   */
  const handleExportChat = useCallback(async () => {
    if (!activeChat) return;
    setExportingChat(true);
    try {
      await exportChatAsPdf({ chat: activeChat, projectId, projectName });
      success('Chat exported as PDF');
    } catch (err) {
      log.error({ err }, 'Failed to export chat as PDF');
      error('Failed to export chat');
    } finally {
      setExportingChat(false);
    }
  }, [activeChat, projectId, projectName, success, error]);

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col h-full bg-card">
        <div className="border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkle size={20} className="text-primary" />
            <h2 className="font-semibold">Chat</h2>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Ask questions about your sources or request analysis
          </p>
        </div>
        <div className="flex-1 p-6 space-y-4">
          {/* Skeleton message bubbles mimicking a chat conversation */}
          <div className="flex justify-end">
            <Skeleton className="h-10 w-2/3 rounded-2xl" />
          </div>
          <div className="flex justify-start gap-3">
            <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          </div>
          <div className="flex justify-end">
            <Skeleton className="h-8 w-1/2 rounded-2xl" />
          </div>
          <div className="flex justify-start gap-3">
            <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
            </div>
          </div>
        </div>
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </div>
    );
  }

  // Empty state - no chats exist
  if (allChats.length === 0 && !activeChat) {
    return (
      <>
        <ChatEmptyState projectName={projectName} onNewChat={handleNewChat} />
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </>
    );
  }

  // Chat list view
  if (showChatList) {
    return (
      <>
        <ChatList
          chats={allChats}
          sendingChatIds={sendingChatIds}
          onSelectChat={handleSelectChat}
          onDeleteChat={handleDeleteChat}
          onRenameChat={handleRenameChat}
          onNewChat={handleNewChat}
        />
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </>
    );
  }

  // Active chat view
  return (
    <div className="flex flex-col h-full min-h-0 min-w-0 w-full bg-card overflow-hidden">
      <ChatHeader
        activeChat={activeChat}
        allChats={allChats}
        activeSources={activeSources}
        totalSources={sources.length}
        chatCosts={chatCosts}
        userUsage={userUsage}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onShowChatList={() => setShowChatList(true)}
        onExportChat={handleExportChat}
        exportingChat={exportingChat}
      />

      {rawMode && activeChat ? (
        <RawMessageView projectId={projectId} chatId={activeChat.id} />
      ) : (
        <ChatMessages
          messages={activeChat?.messages || []}
          sending={sending}
          projectId={projectId}
          chatId={activeChat?.id ?? null}
          streamingAssistantContent={streamingAssistantContent}
          toolProgress={toolProgress}
        />
      )}

      <ChatInput
        message={message}
        partialTranscript={partialTranscript}
        isRecording={isRecording}
        sending={sending}
        transcriptionConfigured={transcriptionConfigured}
        rawMode={rawMode}
        attachments={attachments}
        onMessageChange={setMessage}
        onSend={handleSend}
        onStop={handleStop}
        onMicClick={handleMicClick}
        onToggleRawMode={() => setRawMode((prev) => !prev)}
        onAttachmentsChange={setAttachments}
        onAttachmentError={error}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
