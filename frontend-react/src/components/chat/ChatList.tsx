/**
 * ChatList Component
 * Educational Note: Displays all chats for a project with ability to
 * select, delete, rename, or create new chats. Shows chat metadata like
 * message count and last updated time.
 */

import React, { useState, useMemo } from 'react';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Sparkle, Plus, Clock, Hash, Trash, PencilSimple, MagnifyingGlass, X } from '@phosphor-icons/react';
import type { ChatMetadata } from '../../lib/api/chats';

interface ChatListProps {
  chats: ChatMetadata[];
  onSelectChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
  onRenameChat: (chatId: string, newTitle: string) => void;
  onNewChat: () => void;
}

/**
 * Helper function to format relative time
 */
const formatRelativeTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

export const ChatList: React.FC<ChatListProps> = ({
  chats,
  onSelectChat,
  onDeleteChat,
  onRenameChat,
  onNewChat,
}) => {
  // Search state
  const [searchQuery, setSearchQuery] = useState('');

  // Filter chats by search query (case-insensitive title match)
  const filteredChats = useMemo(
    () => searchQuery
      ? chats.filter((chat) => chat.title.toLowerCase().includes(searchQuery.toLowerCase()))
      : chats,
    [chats, searchQuery]
  );

  // Rename dialog state
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameChatId, setRenameChatId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const handleOpenRename = (chatId: string, currentTitle: string) => {
    setRenameChatId(chatId);
    setRenameValue(currentTitle);
    setRenameDialogOpen(true);
  };

  const handleRenameSubmit = () => {
    if (renameChatId && renameValue.trim()) {
      onRenameChat(renameChatId, renameValue.trim());
      setRenameDialogOpen(false);
      setRenameChatId(null);
      setRenameValue('');
    }
  };

  return (
    <>
    <div className="flex flex-col h-full bg-card">
      {/* Header - matches Sources/Studio/ChatEmptyState structure */}
      <div className="border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkle size={20} className="text-primary" />
          <h2 className="font-semibold">All Chats</h2>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Select a chat to continue or start a new one
        </p>
      </div>

      {/* New Chat Button - in controls section */}
      <div className="px-4 pt-4">
        <Button onClick={onNewChat} variant="soft" className="w-full gap-2">
          <Plus size={16} />
          New Chat
        </Button>
      </div>

      {/* Search input */}
      <div className="px-4 pt-3">
        <div className="relative">
          <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search chats..."
            className="pl-9 pr-9"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>
        {searchQuery && (
          <p className="text-xs text-muted-foreground mt-2">
            Showing {filteredChats.length} of {chats.length} chats
          </p>
        )}
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2">
          {filteredChats.length === 0 && searchQuery ? (
            <div className="text-center py-8">
              <MagnifyingGlass size={32} className="mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No chats found</p>
              <p className="text-xs text-muted-foreground mt-1">
                Try a different search term
              </p>
            </div>
          ) : filteredChats.map((chat) => (
            <div
              key={chat.id}
              className="p-3 border rounded-lg hover:bg-accent transition-colors group"
            >
              <div className="flex items-start justify-between mb-1">
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => onSelectChat(chat.id)}
                >
                  <div className="flex items-center gap-2">
                    <Hash size={16} className="text-muted-foreground" />
                    <h3 className="font-medium text-sm">{chat.title}</h3>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock size={12} />
                    {formatRelativeTime(chat.updated_at)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleOpenRename(chat.id, chat.title);
                    }}
                  >
                    <PencilSimple size={14} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteChat(chat.id);
                    }}
                  >
                    <Trash size={14} className="text-destructive" />
                  </Button>
                </div>
              </div>
              <p
                className="text-xs text-muted-foreground line-clamp-2 cursor-pointer"
                onClick={() => onSelectChat(chat.id)}
              >
                {chat.message_count} messages
              </p>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>

    {/* Rename Dialog */}
    <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>Rename Chat</DialogTitle>
          <DialogDescription>
            Enter a new name for this chat.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <Label htmlFor="chat-name" className="text-sm font-medium">
            Chat Name
          </Label>
          <Input
            id="chat-name"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleRenameSubmit();
              }
            }}
            placeholder="Enter chat name..."
            className="mt-2"
          />
        </div>
        <DialogFooter>
          <Button variant="soft" onClick={() => setRenameDialogOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleRenameSubmit} disabled={!renameValue.trim()}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
};
