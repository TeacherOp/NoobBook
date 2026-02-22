/**
 * ChatHeader Component
 * Educational Note: Header with chat title dropdown and new chat button.
 * Allows quick switching between chats via dropdown menu.
 */

import React from 'react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { Sparkle, Plus, ChatCircle, CaretDown, Hash, Books, DownloadSimple, CircleNotch } from '@phosphor-icons/react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { Button } from '../ui/button';
import type { Chat, ChatMetadata } from '../../lib/api/chats';

interface ChatHeaderProps {
  activeChat: Chat | null;
  allChats: ChatMetadata[];
  activeSources: number;
  totalSources: number;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onShowChatList: () => void;
  onExportChat: () => void;
  exportingChat: boolean;
}

/**
 * Memoized to prevent re-renders when typing in ChatInput
 * Only re-renders when its props actually change
 */
export const ChatHeader: React.FC<ChatHeaderProps> = React.memo(({
  activeChat,
  allChats,
  activeSources,
  totalSources,
  onSelectChat,
  onNewChat,
  onShowChatList,
  onExportChat,
  exportingChat,
}) => {
  return (
    <div className="border-b px-4 py-3">
      {/* Title row - matches Sources/Studio/ChatEmptyState structure */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkle size={20} className="text-primary" />
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-1 hover:opacity-80 transition-opacity">
              <h2 className="font-semibold">{activeChat?.title || 'Chat'}</h2>
              <CaretDown size={14} className="text-muted-foreground" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuItem onClick={onShowChatList}>
                <ChatCircle size={16} className="mr-2" />
                View All Chats
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {allChats.slice(0, 5).map((chat) => (
                <DropdownMenuItem
                  key={chat.id}
                  onClick={() => onSelectChat(chat.id)}
                  className={chat.id === activeChat?.id ? 'bg-accent' : ''}
                >
                  <Hash size={16} className="mr-2" />
                  {chat.title}
                </DropdownMenuItem>
              ))}
              {allChats.length > 5 && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={onShowChatList}>
                    View more...
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onNewChat}>
                <Plus size={16} className="mr-2" />
                New Chat
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="flex items-center gap-2">
          {/* Export chat button */}
          <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={onExportChat}
                disabled={!activeChat || !activeChat.messages?.length || exportingChat}
                className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
              >
                {exportingChat ? (
                  <CircleNotch size={32} weight="bold" className="animate-spin" />
                ) : (
                  <DownloadSimple size={32} weight="bold" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Export as Markdown</TooltipContent>
          </Tooltip>
          </TooltipProvider>

          {/* Source count indicator */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-muted rounded-md">
            <Books size={16} className="text-primary" />
            <span className="text-sm font-medium">{activeSources}/{totalSources}</span>
          </div>
        </div>
      </div>
      {/* Description - matches Sources/Studio */}
      <p className="text-xs text-muted-foreground mt-1">
        Ask questions about your sources or request analysis
      </p>
    </div>
  );
});
