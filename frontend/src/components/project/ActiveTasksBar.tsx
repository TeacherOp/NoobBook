/**
 * ActiveTasksBar Component
 * Educational Note: A floating status bar that shows all active/in-progress
 * tasks for the current project. Polls the backend every 3 seconds and
 * displays source processing, studio generation, and chat sending status.
 * Shows chat names and a "Done" button when a chat finishes processing.
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  CaretUp,
  CaretDown,
  FileText,
  Sparkle,
  ChatCircle,
  Gear,
  CircleNotch,
  StopCircle,
  CheckCircle,
  ArrowRight,
} from '@phosphor-icons/react';
import { API_BASE_URL } from '@/lib/api/client';
import { sourcesAPI } from '@/lib/api/sources';
import axios from 'axios';

interface ActiveTask {
  id: string;
  type: 'source' | 'studio' | 'background' | 'chat';
  label: string;
  detail: string;
  status: string;
  progress?: number;
  created_at: string;
  chatId?: string;
}

interface CompletedChat {
  chatId: string;
  chatName: string;
  completedAt: string;
}

interface ActiveTasksBarProps {
  projectId: string;
  sendingChatIds?: Set<string>;
  chatNames?: Map<string, string>;
  activeChatId?: string | null;
  onOpenChat?: (chatId: string) => void;
}

type TaskIconComponent = React.ComponentType<{ size?: number; className?: string }>;

const TASK_ICONS: Record<string, TaskIconComponent> = {
  source: FileText,
  studio: Sparkle,
  background: Gear,
  chat: ChatCircle,
};


const TaskRow: React.FC<{ task: ActiveTask; onCancel?: (taskId: string) => void }> = ({ task, onCancel }) => {
  const Icon = TASK_ICONS[task.type] || Gear;

  return (
    <div className="group/task flex items-center gap-2.5 px-3 py-2 rounded-lg bg-stone-50 border border-stone-100">
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-amber-50 border border-amber-200 flex items-center justify-center">
        <Icon size={14} className="text-amber-700" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-stone-800 truncate">{task.label}</p>
        <p className="text-[11px] text-stone-500 truncate">{task.detail}</p>
      </div>
      {onCancel && task.type === 'source' ? (
        <button
          onClick={() => onCancel(task.id)}
          className="flex-shrink-0 text-stone-300 group-hover/task:text-red-500 transition-colors"
          title="Stop processing"
        >
          <StopCircle size={16} weight="fill" className="hidden group-hover/task:block" />
          <CircleNotch size={14} className="animate-spin text-amber-600 block group-hover/task:hidden" />
        </button>
      ) : (
        <CircleNotch size={14} className="animate-spin text-amber-600 flex-shrink-0" />
      )}
    </div>
  );
};

const CompletedRow: React.FC<{ chat: CompletedChat; onOpen: () => void; onDismiss: () => void }> = ({ chat, onOpen, onDismiss }) => {
  // Auto-dismiss after 15 seconds
  useEffect(() => {
    const t = setTimeout(onDismiss, 15000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-green-50 border border-green-200">
      <div className="flex-shrink-0 w-7 h-7 rounded-md bg-green-100 border border-green-200 flex items-center justify-center">
        <CheckCircle size={14} className="text-green-700" weight="fill" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-stone-800 truncate">{chat.chatName}</p>
        <p className="text-[11px] text-green-600">Done</p>
      </div>
      <button
        type="button"
        onClick={onOpen}
        className="flex items-center gap-1 text-[11px] font-medium text-amber-700 bg-amber-100 hover:bg-amber-200 px-2 py-1 rounded-md transition-colors flex-shrink-0"
      >
        Open
        <ArrowRight size={11} weight="bold" />
      </button>
    </div>
  );
};

export const ActiveTasksBar: React.FC<ActiveTasksBarProps> = ({
  projectId,
  sendingChatIds,
  chatNames,
  activeChatId,
  onOpenChat,
}) => {
  const [tasks, setTasks] = useState<ActiveTask[]>([]);
  const [completedChats, setCompletedChats] = useState<CompletedChat[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [chatSendStarts, setChatSendStarts] = useState<Map<string, string>>(() => new Map());
  const prevSendingRef = useRef<Set<string>>(new Set());

  const fetchTasks = useCallback(async () => {
    try {
      const resp = await axios.get(`${API_BASE_URL}/projects/${projectId}/active-tasks`);
      if (resp.data.success) {
        setTasks(resp.data.tasks || []);
      }
    } catch {
      // Silently ignore polling errors
    }
  }, [projectId]);

  // Poll every 3 seconds
  useEffect(() => {
    const initialTimeout = window.setTimeout(() => {
      void fetchTasks();
    }, 0);
    const intervalId = window.setInterval(() => {
      void fetchTasks();
    }, 3000);

    return () => {
      window.clearTimeout(initialTimeout);
      window.clearInterval(intervalId);
    };
  }, [fetchTasks]);

  const currentIds = useMemo(() => sendingChatIds || new Set<string>(), [sendingChatIds]);
  const names = useMemo(() => chatNames || new Map<string, string>(), [chatNames]);

  useEffect(() => {
    const nextIds = sendingChatIds || new Set<string>();
    const previousIds = prevSendingRef.current;

    setCompletedChats((prev) => {
      const nextNames = chatNames || new Map<string, string>();
      const newlyCompleted = [...previousIds]
        .filter((id) => id !== activeChatId && !nextIds.has(id) && !prev.some((chat) => chat.chatId === id))
        .map((id) => ({
          chatId: id,
          chatName: nextNames.get(id) || 'Chat',
          completedAt: new Date().toISOString(),
        }));

      return newlyCompleted.length > 0 ? [...prev, ...newlyCompleted] : prev;
    });

    setChatSendStarts((prev) => {
      const next = new Map(prev);
      let changed = false;
      const now = new Date().toISOString();

      nextIds.forEach((id) => {
        if (!next.has(id)) {
          next.set(id, now);
          changed = true;
        }
      });

      [...next.keys()].forEach((id) => {
        if (!nextIds.has(id)) {
          next.delete(id);
          changed = true;
        }
      });

      return changed ? next : prev;
    });

    prevSendingRef.current = new Set(nextIds);
  }, [sendingChatIds, chatNames, activeChatId]);

  // Build the combined task list (API tasks + one entry per sending chat)
  const chatTasks: ActiveTask[] = useMemo(() => Array.from(currentIds).map((chatId) => ({
    id: `__chat_sending_${chatId}__`,
    type: 'chat' as ActiveTask['type'],
    label: names.get(chatId) || 'Chat',
    detail: 'Processing...',
    status: 'sending',
    created_at: chatSendStarts.get(chatId) || new Date().toISOString(),
    chatId,
  })), [currentIds, names, chatSendStarts]);
  const allTasks: ActiveTask[] = [...chatTasks, ...tasks];

  const visibleCompletedChats = useMemo(
    () => completedChats.filter((chat) => chat.chatId !== activeChatId),
    [completedChats, activeChatId]
  );
  const visibleCount = allTasks.length + visibleCompletedChats.length;

  const dismissCompleted = useCallback((chatId: string) => {
    setCompletedChats(prev => prev.filter(c => c.chatId !== chatId));
  }, []);

  if (visibleCount === 0) return null;

  return (
    <div
      className="fixed bottom-14 right-6 z-40 transition-all duration-300 ease-out opacity-100 translate-y-0"
      style={{ maxWidth: 340, width: '100%' }}
    >
      <div className="bg-white rounded-xl shadow-lg shadow-stone-200/60 border border-stone-200 overflow-hidden">
        {/* Header — always visible */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-2 px-3.5 py-2.5 hover:bg-stone-50 transition-colors text-left"
        >
          <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
            {allTasks.length > 0 ? (
              <CircleNotch size={13} className="animate-spin text-amber-600" weight="bold" />
            ) : (
              <CheckCircle size={13} className="text-green-600" weight="fill" />
            )}
          </div>
          <span className="text-[13px] font-semibold text-stone-700 flex-1">
            Active Tasks
          </span>
          <span className="text-[11px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
            {visibleCount}
          </span>
          <span className="text-stone-400 ml-0.5">
            {expanded ? <CaretUp size={13} /> : <CaretDown size={13} />}
          </span>
        </button>

        {/* Expanded task list */}
        <div
          className={`overflow-hidden transition-all duration-200 ease-out ${
            expanded ? 'max-h-[400px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          <div className="px-2.5 pb-2.5 space-y-1.5 max-h-[350px] overflow-y-auto">
            {/* Active tasks */}
            {allTasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onCancel={task.type === 'source' ? async (sourceId) => {
                  try {
                    await sourcesAPI.cancelProcessing(projectId, sourceId);
                  } catch { /* ignore */ }
                } : undefined}
              />
            ))}
            {/* Completed chats with "Open" button */}
            {visibleCompletedChats.map((chat) => (
              <CompletedRow
                key={chat.chatId}
                chat={chat}
                onOpen={() => {
                  onOpenChat?.(chat.chatId);
                  dismissCompleted(chat.chatId);
                }}
                onDismiss={() => dismissCompleted(chat.chatId)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
