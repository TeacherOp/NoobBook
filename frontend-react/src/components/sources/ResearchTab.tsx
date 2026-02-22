/**
 * ResearchTab Component
 * Educational Note: Handles adding sources via deep research.
 * User provides a topic, description, and optional links.
 * The system researches and generates a comprehensive source document.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { MagnifyingGlass, CircleNotch, Plus, X } from '@phosphor-icons/react';

interface ResearchTabProps {
  onAddResearch: (topic: string, description: string, links: string[]) => Promise<void>;
  isAtLimit: boolean;
}

const MIN_DESCRIPTION_LENGTH = 50;

export const ResearchTab: React.FC<ResearchTabProps> = ({ onAddResearch, isAtLimit }) => {
  const [topic, setTopic] = useState('');
  const [description, setDescription] = useState('');
  const [links, setLinks] = useState<string[]>([]);
  const [newLink, setNewLink] = useState('');
  const [researching, setResearching] = useState(false);

  /**
   * Handle starting deep research
   */
  const handleResearch = async () => {
    if (!isValid) return;

    setResearching(true);
    try {
      await onAddResearch(topic.trim(), description.trim(), links);
      setTopic('');
      setDescription('');
      setLinks([]);
      setNewLink('');
    } finally {
      setResearching(false);
    }
  };

  /**
   * Add a new link to the list
   */
  const handleAddLink = () => {
    const trimmedLink = newLink.trim();
    if (!trimmedLink) return;

    // Basic URL validation
    try {
      new URL(trimmedLink);
      if (!links.includes(trimmedLink)) {
        setLinks([...links, trimmedLink]);
      }
      setNewLink('');
    } catch {
      // Invalid URL - try adding https:// prefix
      try {
        const withProtocol = `https://${trimmedLink}`;
        new URL(withProtocol);
        if (!links.includes(withProtocol)) {
          setLinks([...links, withProtocol]);
        }
        setNewLink('');
      } catch {
        // Still invalid, ignore
      }
    }
  };

  /**
   * Remove a link from the list
   */
  const handleRemoveLink = (linkToRemove: string) => {
    setLinks(links.filter(link => link !== linkToRemove));
  };

  /**
   * Handle Enter key in link input
   */
  const handleLinkKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddLink();
    }
  };

  const isTopicValid = topic.trim().length > 0;
  const isDescriptionValid = description.trim().length >= MIN_DESCRIPTION_LENGTH;
  const isValid = isTopicValid && isDescriptionValid;
  const descriptionLength = description.trim().length;

  return (
    <div className="space-y-4">
      {/* Topic Input */}
      <div>
        <label className="text-sm font-medium mb-2 block">
          Research Topic <span className="text-destructive">*</span>
        </label>
        <Input
          placeholder="e.g., Latest advancements in quantum computing"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={isAtLimit || researching}
        />
        <p className="text-xs text-muted-foreground mt-1">
          What topic should be researched?
        </p>
      </div>

      {/* Description Input */}
      <div>
        <label className="text-sm font-medium mb-2 block">
          Description / Focus Areas <span className="text-destructive">*</span>
        </label>
        <textarea
          className="w-full h-24 p-3 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder="Describe specific aspects you want covered, questions to answer, or areas to focus on..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isAtLimit || researching}
        />
        <div className="flex justify-between mt-1">
          <p className="text-xs text-muted-foreground">
            Provide context for the research
          </p>
          <p className={`text-xs ${descriptionLength >= MIN_DESCRIPTION_LENGTH ? 'text-green-600' : 'text-muted-foreground'}`}>
            {descriptionLength}/{MIN_DESCRIPTION_LENGTH} characters min
          </p>
        </div>
      </div>

      {/* Links Input */}
      <div>
        <label className="text-sm font-medium mb-2 block">
          Reference Links <span className="text-muted-foreground font-normal">(optional)</span>
        </label>
        <div className="flex gap-2">
          <Input
            placeholder="https://example.com/article"
            value={newLink}
            onChange={(e) => setNewLink(e.target.value)}
            onKeyDown={handleLinkKeyDown}
            disabled={isAtLimit || researching}
            className="flex-1"
          />
          <Button
            type="button"
            variant="soft"
            size="icon"
            onClick={handleAddLink}
            disabled={isAtLimit || researching || !newLink.trim()}
          >
            <Plus size={16} />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Add specific URLs you want the research to include
        </p>

        {/* Links List */}
        {links.length > 0 && (
          <div className="mt-2 space-y-1">
            {links.map((link, index) => (
              <div
                key={index}
                className="flex items-center gap-2 p-2 bg-muted/50 rounded text-xs"
              >
                <span className="flex-1 truncate text-muted-foreground">{link}</span>
                <button
                  onClick={() => handleRemoveLink(link)}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                  disabled={researching}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="bg-muted/50 rounded-lg p-3 text-sm text-muted-foreground">
        <p className="font-medium text-foreground mb-1">How Deep Research works:</p>
        <ul className="list-disc list-inside space-y-1 text-xs">
          <li>AI agent searches the web for relevant information</li>
          <li>Analyzes any provided reference links</li>
          <li>Synthesizes findings into a comprehensive document</li>
          <li>Creates a source you can query in your chats</li>
        </ul>
      </div>

      {/* Research Button */}
      <Button
        className="w-full"
        onClick={handleResearch}
        disabled={isAtLimit || researching || !isValid}
      >
        {researching ? (
          <>
            <CircleNotch size={16} className="mr-2 animate-spin" />
            Researching...
          </>
        ) : (
          <>
            <MagnifyingGlass size={16} className="mr-2" />
            Start Deep Research
          </>
        )}
      </Button>
    </div>
  );
};
