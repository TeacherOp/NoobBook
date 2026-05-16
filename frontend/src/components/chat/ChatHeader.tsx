/**
 * ChatHeader Component
 * Educational Note: Header with chat title dropdown and new chat button.
 * Allows quick switching between chats via dropdown menu.
 */

import React, { useMemo } from 'react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { Sparkle, Plus, ChatCircle, CaretDown, Hash, Books, DownloadSimple, CircleNotch, CurrencyDollar } from '@phosphor-icons/react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { Button } from '../ui/button';
import { usePermissions } from '@/contexts/PermissionsContext';
import type { Chat, ChatMetadata } from '../../lib/api/chats';
import type { CostTracking } from '../../lib/api/projects';
import type { UserUsage } from '../../lib/api/settings';
import { cn } from '../../lib/utils';

interface ChatHeaderProps {
  activeChat: Chat | null;
  allChats: ChatMetadata[];
  activeSources: number;
  totalSources: number;
  chatCosts: CostTracking | null;
  userUsage: UserUsage | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onShowChatList: () => void;
  onExportChat: () => void;
  exportingChat: boolean;
}

// Cost formatters — mirrors ProjectHeader so the two badges look identical
const formatCost = (cost: number): string => {
  if (cost < 0.01) return '<$0.01';
  return `$${cost.toFixed(2)}`;
};

const formatCostWithSymbol = (cost: number): string => `$${cost.toFixed(6)}`;

const formatTokens = (count: number): string => {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return count.toString();
};

/**
 * Memoized to prevent re-renders when typing in ChatInput
 * Only re-renders when its props actually change
 */
export const ChatHeader: React.FC<ChatHeaderProps> = React.memo(({
  activeChat,
  allChats,
  activeSources,
  totalSources,
  chatCosts,
  userUsage,
  onSelectChat,
  onNewChat,
  onShowChatList,
  onExportChat,
  exportingChat,
}) => {
  const { hasPermission } = usePermissions();

  // Platform-aware shortcut glyph: ⌘ on Mac, Ctrl elsewhere. Memoised so the
  // tooltip body doesn't recompute on every parent re-render. navigator.platform
  // is deprecated; prefer userAgentData.platform (Chromium-only) with a
  // userAgent-string fallback for Safari / Firefox.
  const shortcutLabel = useMemo(() => {
    if (typeof navigator === 'undefined') return 'Ctrl+⇧+O';
    const uaDataPlatform = (
      navigator as Navigator & { userAgentData?: { platform?: string } }
    ).userAgentData?.platform;
    const platformHint = uaDataPlatform || navigator.userAgent || '';
    const isMac = /Mac|iPhone|iPad|iPod/i.test(platformHint);
    return isMac ? '⌘⇧O' : 'Ctrl+⇧+O';
  }, []);

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
          {/* Prominent "New chat" button — Claude-app parity (Sno 51 / GH #254).
              Same handler as the dropdown item below; the dropdown stays for
              muscle memory but this is the one-click affordance. */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="soft"
                  size="sm"
                  onClick={onNewChat}
                  className="h-8 gap-1.5"
                >
                  <Plus size={14} weight="bold" />
                  <span>New chat</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                New chat
                <kbd className="ml-1.5 text-xs opacity-70">{shortcutLabel}</kbd>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Export chat button — hidden when chat_export permission is disabled */}
          {hasPermission("chat_features", "chat_export") && (
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
              <TooltipContent>Export as PDF</TooltipContent>
            </Tooltip>
            </TooltipProvider>
          )}

          {/* Source count indicator */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-muted rounded-md">
            <Books size={16} className="text-primary" />
            <span className="text-sm font-medium">{activeSources}/{totalSources}</span>
          </div>

          {/* User spending limit progress — compact bar */}
          {userUsage && userUsage.cost_limit && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-2 px-2 py-1 bg-muted/50 rounded-md cursor-default sm:min-w-[90px]">
                    <div className="flex-1 space-y-0.5 min-w-[44px]">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-medium text-muted-foreground tabular-nums whitespace-nowrap">
                          <span className="hidden sm:inline">${userUsage.current_spend.toFixed(2)}/${userUsage.cost_limit}</span>
                          <span className="sm:hidden">${userUsage.current_spend.toFixed(0)}/${userUsage.cost_limit}</span>
                        </span>
                      </div>
                      <div className="h-1 w-full bg-stone-200 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            userUsage.usage_percent >= 90 ? 'bg-red-500'
                              : userUsage.usage_percent >= 70 ? 'bg-amber-500'
                              : 'bg-emerald-500',
                          )}
                          style={{ width: `${Math.min(userUsage.usage_percent, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                  <p>Budget: ${userUsage.current_spend.toFixed(2)} of ${userUsage.cost_limit.toFixed(2)} ({userUsage.usage_percent.toFixed(1)}%)</p>
                  {userUsage.reset_frequency && <p className="text-muted-foreground">Resets {userUsage.reset_frequency}</p>}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}

          {/* Per-chat cost badge — shows only when this chat has spent something */}
          {chatCosts && chatCosts.total_cost > 0 && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1.5 px-2 py-1 bg-muted/50 rounded-md cursor-default">
                    <CurrencyDollar size={14} className="text-muted-foreground" />
                    <span className="text-sm text-muted-foreground font-medium">
                      {formatCost(chatCosts.total_cost)}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="p-3">
                  <div className="space-y-2 text-xs">
                    <p className="font-semibold text-sm mb-2">Chat Usage Breakdown</p>

                    {chatCosts.by_model.opus && (chatCosts.by_model.opus.input_tokens > 0 || chatCosts.by_model.opus.output_tokens > 0) && (
                      <div className="space-y-1">
                        <p className="font-medium">Opus</p>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                          <span>Input:</span>
                          <span>{formatTokens(chatCosts.by_model.opus.input_tokens)} tokens</span>
                          <span>Output:</span>
                          <span>{formatTokens(chatCosts.by_model.opus.output_tokens)} tokens</span>
                          <span>Cost:</span>
                          <span className="font-medium text-foreground">{formatCostWithSymbol(chatCosts.by_model.opus.cost)}</span>
                        </div>
                      </div>
                    )}

                    {(chatCosts.by_model.sonnet.input_tokens > 0 || chatCosts.by_model.sonnet.output_tokens > 0) && (
                      <div className="space-y-1">
                        <p className="font-medium">Sonnet</p>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                          <span>Input:</span>
                          <span>{formatTokens(chatCosts.by_model.sonnet.input_tokens)} tokens</span>
                          <span>Output:</span>
                          <span>{formatTokens(chatCosts.by_model.sonnet.output_tokens)} tokens</span>
                          <span>Cost:</span>
                          <span className="font-medium text-foreground">{formatCostWithSymbol(chatCosts.by_model.sonnet.cost)}</span>
                        </div>
                      </div>
                    )}

                    {(chatCosts.by_model.haiku.input_tokens > 0 || chatCosts.by_model.haiku.output_tokens > 0) && (
                      <div className="space-y-1">
                        <p className="font-medium">Haiku</p>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                          <span>Input:</span>
                          <span>{formatTokens(chatCosts.by_model.haiku.input_tokens)} tokens</span>
                          <span>Output:</span>
                          <span>{formatTokens(chatCosts.by_model.haiku.output_tokens)} tokens</span>
                          <span>Cost:</span>
                          <span className="font-medium text-foreground">{formatCostWithSymbol(chatCosts.by_model.haiku.cost)}</span>
                        </div>
                      </div>
                    )}

                    <div className="border-t pt-2 mt-2">
                      <div className="flex justify-between font-medium">
                        <span>Total:</span>
                        <span>{formatCostWithSymbol(chatCosts.total_cost)}</span>
                      </div>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>
      {/* Description - matches Sources/Studio */}
      <p className="text-xs text-muted-foreground mt-1">
        Ask questions about your sources or request analysis
      </p>
    </div>
  );
});
