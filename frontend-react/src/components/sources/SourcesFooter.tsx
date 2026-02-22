/**
 * SourcesFooter Component
 * Educational Note: Displays source statistics, progress bar, and limit warning.
 * Shows count/limit ratio and total file size.
 */

import React from 'react';
import { Progress } from '../ui/progress';
import { WarningCircle } from '@phosphor-icons/react';
import { formatFileSize, MAX_SOURCES } from '../../lib/api/sources';

interface SourcesFooterProps {
  sourcesCount: number;
  totalSize: number;
}

export const SourcesFooter: React.FC<SourcesFooterProps> = ({
  sourcesCount,
  totalSize,
}) => {
  const isAtLimit = sourcesCount >= MAX_SOURCES;

  return (
    <div className="px-4 pb-4 space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {sourcesCount} / {MAX_SOURCES} sources
        </span>
        <span>{formatFileSize(totalSize)} total</span>
      </div>
      <Progress value={(sourcesCount / MAX_SOURCES) * 100} className="h-1" />
      {isAtLimit && (
        <p className="text-xs text-destructive flex items-center gap-1">
          <WarningCircle size={12} />
          Source limit reached
        </p>
      )}
    </div>
  );
};
