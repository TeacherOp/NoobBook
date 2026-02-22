/**
 * EmailListItem Component
 * Educational Note: Renders a saved email template in the Generated Content list.
 */

import React from 'react';
import { ShareNetwork } from '@phosphor-icons/react';
import type { EmailJob } from '@/lib/api/studio';

interface EmailListItemProps {
  job: EmailJob;
  onClick: () => void;
}

export const EmailListItem: React.FC<EmailListItemProps> = ({ job, onClick }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-blue-500/10 rounded-md flex-shrink-0">
        <ShareNetwork size={16} className="text-blue-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.template_name || 'Email Template'}
        </p>
      </div>
    </div>
  );
};
