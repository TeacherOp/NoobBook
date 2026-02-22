/**
 * ConfigErrorBanner Component
 * Educational Note: Inline error banner shown in the Studio panel when a
 * required API key (e.g., Gemini) is missing. More visible than a toast —
 * appears right where the user clicked so they know what to do.
 */

import React from 'react';
import { WarningCircle } from '@phosphor-icons/react';

interface ConfigErrorBannerProps {
  message: string | null;
}

export const ConfigErrorBanner: React.FC<ConfigErrorBannerProps> = ({ message }) => {
  if (!message) return null;

  return (
    <div className="p-2.5 bg-amber-500/10 rounded-md border border-amber-500/30">
      <div className="flex items-start gap-2">
        <WarningCircle size={16} weight="fill" className="text-amber-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
            API Key Required
          </p>
          <p className="text-[11px] text-amber-600/80 dark:text-amber-400/70 mt-0.5">
            {message}
          </p>
        </div>
      </div>
    </div>
  );
};
