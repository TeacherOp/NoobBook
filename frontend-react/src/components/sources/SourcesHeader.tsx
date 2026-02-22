/**
 * SourcesHeader Component
 * Educational Note: Header section matching Chat/Studio header style.
 * Title + description in header, controls (search, add) in separate section below.
 */

import React from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Plus, MagnifyingGlass, Books } from '@phosphor-icons/react';

interface SourcesHeaderProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onAddClick: () => void;
  isAtLimit: boolean;
}

export const SourcesHeader: React.FC<SourcesHeaderProps> = ({
  searchQuery,
  onSearchChange,
  onAddClick,
  isAtLimit,
}) => {
  return (
    <div>
      {/* Header Section - matches Chat/Studio header style */}
      <div className="px-4 py-3 pr-12 border-b">
        <div className="flex items-center gap-2">
          <Books size={20} className="text-primary" />
          <h2 className="font-semibold">Sources</h2>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          All sources for your project
        </p>
      </div>

      {/* Controls Section */}
      <div className="p-4 space-y-3">
        {/* Search */}
        <div className="relative">
          <MagnifyingGlass size={16} className="absolute left-2 top-2.5 text-muted-foreground" />
          <Input
            placeholder="Search sources..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-8 h-9"
          />
        </div>

        {/* Add Source Button */}
        <Button
          onClick={onAddClick}
          className="w-full gap-2"
          variant="soft"
          size="sm"
          disabled={isAtLimit}
        >
          <Plus size={16} />
          Add sources
        </Button>
      </div>
    </div>
  );
};
