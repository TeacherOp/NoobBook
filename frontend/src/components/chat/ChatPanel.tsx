/**
 * ChatPanel Component
 * Educational Note: Main orchestrator for the chat interface.
 * Composes smaller components (ChatHeader, ChatMessages, ChatInput, etc.)
 * and manages chat state and API interactions.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Sparkle } from '@phosphor-icons/react';
import { Skeleton } from '../ui/skeleton';
import { chatsAPI } from '@/lib/api/chats';
import type { Chat, ChatMetadata, StudioSignal } from '@/lib/api/chats';
import { sourcesAPI, type Source } from '@/lib/api/sources';
import { useToast, ToastContainer } from '../ui/toast';
import { useVoiceRecording } from '../hooks/useVoiceRecording';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { ChatList } from './ChatList';
import { ChatEmptyState } from './ChatEmptyState';
import { RawMessageView } from './RawMessageView';
import { exportChatAsMarkdown } from '@/lib/exportChatMarkdown';
import { createLogger } from '@/lib/logger';

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
  const { toasts, dismissToast, success, error } = useToast();

  // Chat state
  const [message, setMessage] = useState('');
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [showChatList, setShowChatList] = useState(false);
  const [allChats, setAllChats] = useState<ChatMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  // Derive sending state for current chat from parent-owned Set
  const sending = activeChat ? sendingChatIds.has(activeChat.id) : false;
  const [exportingChat, setExportingChat] = useState(false);
  const [rawMode, setRawMode] = useState(false);
  // AbortController for cancelling in-flight chat requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // Sources state for header display
  const [sources, setSources] = useState<Source[]>([]);

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
      log.error({ err }, 'failed to Lloading sourcesE');
    }
  };

  /**
   * Load full chat data including all messages
   */
  const loadFullChat = async (chatId: string) => {
    try {
      const chat = await chatsAPI.getChat(projectId, chatId);
      setActiveChat(chat);
      // Notify parent of per-chat source selection
      onActiveChatChange(chat.id, chat.selected_source_ids ?? []);
    } catch (err) {
      log.error({ err }, 'failed to load chat');
      error('Failed to load chat');
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
      log.error({ err }, 'failed to Lloading chatsE');
      error('Failed to load chats');
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

  /**
   * Send a message and get AI response
   * Educational Note: We add the user message optimistically to the UI
   * before the API call, so users see their message immediately.
   */
  const handleSend = async () => {
    if (!message.trim() || !activeChat || sending) return;

    const userMessage = message.trim();
    const sendingChatId = activeChat.id;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setMessage('');
    onAddSendingChat(sendingChatId, activeChat.title);

    // Optimistically add user message to UI immediately
    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      role: 'user' as const,
      content: userMessage,
      timestamp: new Date().toISOString(),
    };

    setActiveChat((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...prev.messages, tempUserMessage],
      };
    });

    // Add a temporary streaming assistant message
    const tempAssistantId = `streaming-${Date.now()}`;
    const tempAssistantMessage = {
      id: tempAssistantId,
      role: 'assistant' as const,
      content: '',
      timestamp: new Date().toISOString(),
    };

    setActiveChat((prev) => {
      if (!prev) return null;
      return { ...prev, messages: [...prev.messages, tempAssistantMessage] };
    });

    try {
      const chatId = activeChat.id;

      const result = await chatsAPI.sendMessageStream(
        projectId,
        chatId,
        userMessage,
        (type, data) => {
          if (type === 'text_delta') {
            // Append text chunk to the streaming assistant message
            const chunk = (data as { content?: string }).content || '';
            setActiveChat((prev) => {
              if (!prev) return null;
              return {
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === tempAssistantId
                    ? { ...m, content: m.content + chunk }
                    : m
                ),
              };
            });
          }
          // status events are visible in ActiveTasksBar already
        },
        controller.signal,
      );

      // Replace both temp messages with final stored messages from backend
      setActiveChat((prev) => {
        if (!prev) return null;
        const cleaned = prev.messages.filter(
          (m) => m.id !== tempUserMessage.id && m.id !== tempAssistantId
        );
        return {
          ...prev,
          messages: [...cleaned, result.user_message, result.assistant_message],
          updated_at: new Date().toISOString(),
        };
      });

      await loadChats();
      onCostsChange?.();

      // Fetch updated chat for signals and title
      setTimeout(async () => {
        try {
          const updatedChat = await chatsAPI.getChat(projectId, chatId);
          setActiveChat(prev => prev && prev.id === chatId
            ? { ...prev, studio_signals: updatedChat.studio_signals || [] }
            : prev
          );
        } catch { /* non-critical */ }
      }, 1000);

      setTimeout(async () => {
        try {
          const updatedChat = await chatsAPI.getChat(projectId, chatId);
          setActiveChat(prev => prev && prev.id === chatId
            ? { ...prev, title: updatedChat.title, studio_signals: updatedChat.studio_signals || [] }
            : prev
          );
          setAllChats(prev => prev.map(c =>
            c.id === chatId ? { ...c, title: updatedChat.title } : c
          ));
        } catch { /* non-critical */ }
      }, 4000);
    } catch (err) {
      const isAborted = err instanceof Error && (err.name === 'CanceledError' || err.name === 'AbortError');
      if (isAborted) {
        log.info('Chat request stopped by user');
      } else {
        log.error({ err }, 'failed to send message');
        error('Failed to send message');
      }
      // Remove both temp messages on error/abort
      setActiveChat((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          messages: prev.messages.filter(
            (m) => m.id !== tempUserMessage.id && m.id !== tempAssistantId
          ),
        };
      });
    } finally {
      onRemoveSendingChat(sendingChatId);
      abortControllerRef.current = null;
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
  };

  /**
   * Create a new chat
   */
  const handleNewChat = async () => {
    try {
      const newChat = await chatsAPI.createChat(projectId, 'New Chat');
      await loadChats();
      await loadFullChat(newChat.id);
      // New chats start with no sources selected (loadFullChat will call onActiveChatChange)
      setShowChatList(false);
      success('New chat created');
    } catch (err) {
      log.error({ err }, 'failed to Lcreating chatE');
      error('Failed to create chat');
    }
  };

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

      // If the deleted chat was active, clear it and reset source selection
      if (activeChat?.id === chatId) {
        setActiveChat(null);
        onActiveChatChange(null, []);
      }

      await loadChats();
      success('Chat deleted');
    } catch (err) {
      log.error({ err }, 'failed to Ldeleting chatE');
      error('Failed to delete chat');
    }
  };

  /**
   * Rename a chat
   */
  const handleRenameChat = async (chatId: string, newTitle: string) => {
    try {
      await chatsAPI.updateChat(projectId, chatId, newTitle);
      await loadChats();

      // Update active chat if it was renamed
      if (activeChat?.id === chatId) {
        setActiveChat(prev => prev ? { ...prev, title: newTitle } : null);
      }

      success('Chat renamed');
    } catch (err) {
      log.error({ err }, 'failed to Lrenaming chatE');
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
   * Export the active chat as a Markdown file
   */
  const handleExportChat = useCallback(async () => {
    if (!activeChat) return;
    setExportingChat(true);
    try {
      await exportChatAsMarkdown({ chat: activeChat, projectId, projectName });
      success('Chat exported as Markdown');
    } catch (err) {
      log.error({ err }, 'failed to Lexporting chatE');
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
        />
      )}

      <ChatInput
        message={message}
        partialTranscript={partialTranscript}
        isRecording={isRecording}
        sending={sending}
        transcriptionConfigured={transcriptionConfigured}
        rawMode={rawMode}
        onMessageChange={setMessage}
        onSend={handleSend}
        onStop={handleStop}
        onMicClick={handleMicClick}
        onToggleRawMode={() => setRawMode((prev) => !prev)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
