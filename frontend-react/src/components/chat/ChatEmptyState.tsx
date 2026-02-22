/**
 * ChatEmptyState Component
 * Educational Note: Shown when no chats exist for a project.
 * Provides a clear call-to-action to start a new chat.
 */

import React from 'react';
import { Button } from '../ui/button';
import { Sparkle, ChatCircle, Plus } from '@phosphor-icons/react';

interface ChatEmptyStateProps {
  projectName: string;
  onNewChat: () => void;
}

export const ChatEmptyState: React.FC<ChatEmptyStateProps> = ({
  projectName: _projectName,
  onNewChat,
}) => {
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

      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <ChatCircle size={48} className="mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">No chats yet</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Start a conversation to explore your project sources
          </p>
          <Button onClick={onNewChat} className="gap-2">
            <Plus size={16} />
            Start New Chat
          </Button>
        </div>
      </div>
    </div>
  );
};
