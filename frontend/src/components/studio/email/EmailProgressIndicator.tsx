/**
 * EmailProgressIndicator Component
 * Educational Note: Shows real-time progress during email template generation.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { EmailJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface EmailProgressIndicatorProps {
  currentEmailJob: EmailJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const EmailProgressIndicator: React.FC<EmailProgressIndicatorProps> = ({
  currentEmailJob,
  projectId,
}) => {
  if (!currentEmailJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentEmailJob?.id) return;
    await cancelStudioJob(projectId, currentEmailJob.id);
  };

  return (
    <div className="p-2 bg-blue-500/5 rounded-md border border-blue-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-blue-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentEmailJob.source_name || 'Generating email template...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentEmailJob.status_message || 'Starting...'}
          </p>
        </div>
        {projectId && currentEmailJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
