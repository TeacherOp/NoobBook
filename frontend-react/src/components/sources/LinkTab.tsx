/**
 * LinkTab Component
 * Educational Note: Handles adding sources via URL (website or YouTube).
 * URLs are stored as .link files - content fetching happens separately.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Plus, YoutubeLogo, CircleNotch, Globe } from '@phosphor-icons/react';

interface LinkTabProps {
  onAddUrl: (url: string) => Promise<void>;
  isAtLimit: boolean;
}

export const LinkTab: React.FC<LinkTabProps> = ({ onAddUrl, isAtLimit }) => {
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [addingWebsite, setAddingWebsite] = useState(false);
  const [addingYoutube, setAddingYoutube] = useState(false);

  /**
   * Handle adding a website URL
   */
  const handleAddWebsite = async () => {
    if (!websiteUrl.trim()) return;

    let url = websiteUrl.trim();
    // Auto-prepend https:// if no protocol specified
    if (!/^https?:\/\//i.test(url)) {
      url = `https://${url}`;
    }

    setAddingWebsite(true);
    try {
      await onAddUrl(url);
      setWebsiteUrl('');
    } finally {
      setAddingWebsite(false);
    }
  };

  /**
   * Handle adding a YouTube URL
   */
  const handleAddYoutube = async () => {
    if (!youtubeUrl.trim()) return;

    let url = youtubeUrl.trim();
    // Auto-prepend https:// if no protocol specified
    if (!/^https?:\/\//i.test(url)) {
      url = `https://${url}`;
    }

    setAddingYoutube(true);
    try {
      await onAddUrl(url);
      setYoutubeUrl('');
    } finally {
      setAddingYoutube(false);
    }
  };

  /**
   * Handle Enter key press
   */
  const handleKeyPress = (
    e: React.KeyboardEvent,
    handler: () => Promise<void>
  ) => {
    if (e.key === 'Enter') {
      handler();
    }
  };

  return (
    <div className="space-y-6">
      {/* Website URL Input */}
      <div>
        <label className="text-sm font-medium mb-2 block flex items-center gap-2">
          <Globe size={16} />
          Website URL
        </label>
        <div className="flex gap-2">
          <Input
            placeholder="https://example.com"
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            onKeyDown={(e) => handleKeyPress(e, handleAddWebsite)}
            disabled={isAtLimit || addingWebsite}
          />
          <Button
            size="icon"
            variant="soft"
            onClick={handleAddWebsite}
            disabled={isAtLimit || addingWebsite || !websiteUrl.trim()}
          >
            {addingWebsite ? (
              <CircleNotch size={16} className="animate-spin" />
            ) : (
              <Plus size={16} />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Add any website URL to use as a source
        </p>
      </div>

      {/* YouTube Video Input */}
      <div>
        <label className="text-sm font-medium mb-2 block flex items-center gap-2">
          <YoutubeLogo size={16} />
          YouTube Video
        </label>
        <div className="flex gap-2">
          <Input
            placeholder="https://youtube.com/watch?v=..."
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            onKeyDown={(e) => handleKeyPress(e, handleAddYoutube)}
            disabled={isAtLimit || addingYoutube}
          />
          <Button
            size="icon"
            variant="soft"
            onClick={handleAddYoutube}
            disabled={isAtLimit || addingYoutube || !youtubeUrl.trim()}
          >
            {addingYoutube ? (
              <CircleNotch size={16} className="animate-spin" />
            ) : (
              <Plus size={16} />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Add YouTube video URLs (transcript will be extracted)
        </p>
      </div>
    </div>
  );
};
