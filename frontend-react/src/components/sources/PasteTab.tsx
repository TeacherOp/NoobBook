/**
 * PasteTab Component
 * Educational Note: Handles adding sources by pasting text content.
 * Text is stored as a .txt file - the raw content IS the processed content.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ClipboardText, CircleNotch } from '@phosphor-icons/react';

interface PasteTabProps {
  onAddText: (content: string, name: string) => Promise<void>;
  isAtLimit: boolean;
}

export const PasteTab: React.FC<PasteTabProps> = ({ onAddText, isAtLimit }) => {
  const [content, setContent] = useState('');
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);

  /**
   * Handle adding pasted text
   */
  const handleAddText = async () => {
    if (!content.trim() || !name.trim()) return;

    setAdding(true);
    try {
      await onAddText(content.trim(), name.trim());
      setContent('');
      setName('');
    } finally {
      setAdding(false);
    }
  };

  const isValid = content.trim() && name.trim();

  return (
    <div className="space-y-4">
      {/* Name Input */}
      <div>
        <label className="text-sm font-medium mb-2 block">
          Source Name <span className="text-destructive">*</span>
        </label>
        <Input
          placeholder="e.g., Meeting Notes, Research Summary"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isAtLimit || adding}
        />
      </div>

      {/* Text Paste Area */}
      <div>
        <label className="text-sm font-medium mb-2 block">
          Content <span className="text-destructive">*</span>
        </label>
        <textarea
          className="w-full h-40 p-3 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder="Paste your text content here..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={isAtLimit || adding}
        />
        <p className="text-xs text-muted-foreground mt-1">
          {content.length.toLocaleString()} characters
        </p>
      </div>

      {/* Add Button */}
      <Button
        className="w-full"
        onClick={handleAddText}
        disabled={isAtLimit || adding || !isValid}
      >
        {adding ? (
          <>
            <CircleNotch size={16} className="mr-2 animate-spin" />
            Adding...
          </>
        ) : (
          <>
            <ClipboardText size={16} className="mr-2" />
            Add Pasted Content
          </>
        )}
      </Button>
    </div>
  );
};
