/**
 * FreshdeskTab Component
 * Educational Note: Adds a Freshdesk ticket source to the project.
 * Simpler than DatabaseTab since there's no connection selection —
 * Freshdesk credentials are configured globally in API Keys settings.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { CircleNotch, Plus } from '@phosphor-icons/react';

interface FreshdeskTabProps {
  isAtLimit: boolean;
  onAddFreshdesk: (name?: string, description?: string) => Promise<void>;
}

export const FreshdeskTab: React.FC<FreshdeskTabProps> = ({ isAtLimit, onAddFreshdesk }) => {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleAdd = async () => {
    setAdding(true);
    try {
      await onAddFreshdesk(
        name.trim() || undefined,
        description.trim() || undefined
      );
      setName('');
      setDescription('');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm">
        Sync your Freshdesk tickets into NoobBook for AI-powered analysis.
      </p>
      <p className="text-xs text-muted-foreground">
        Requires Freshdesk API Key and Domain configured in Admin Settings → API Keys.
      </p>

      <div className="space-y-2">
        <label className="text-sm font-medium block">Display name (optional)</label>
        <Input
          placeholder="Freshdesk Tickets"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isAtLimit || adding}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium block">Description (optional)</label>
        <Input
          placeholder="Support tickets from Freshdesk"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isAtLimit || adding}
        />
      </div>

      <Button
        onClick={handleAdd}
        disabled={isAtLimit || adding}
      >
        {adding ? (
          <>
            <CircleNotch size={16} className="mr-2 animate-spin" />
            Adding...
          </>
        ) : (
          <>
            <Plus size={16} className="mr-2" />
            Add Freshdesk source
          </>
        )}
      </Button>

      <p className="text-xs text-muted-foreground">
        NoobBook will sync the last 90 days of tickets, generate a summary, and enable SQL-based ticket analysis in chat.
      </p>
    </div>
  );
};
