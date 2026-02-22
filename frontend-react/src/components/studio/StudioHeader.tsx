/**
 * StudioHeader Component
 * Educational Note: Header section matching Chat/Sources header style.
 * Consistent title + description layout across all panels.
 */

import React from 'react';
import { MagicWand } from '@phosphor-icons/react';

export const StudioHeader: React.FC = () => {
  return (
    <div className="px-4 py-3 pl-12 border-b">
      <div className="flex items-center gap-2">
        <MagicWand size={20} className="text-primary" />
        <h2 className="font-semibold">Studio</h2>
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        Generate content from your sources
      </p>
    </div>
  );
};
