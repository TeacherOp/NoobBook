/**
 * QuizProgressIndicator Component
 * Educational Note: Shows real-time progress during quiz generation.
 * Orange theme distinguishes quizzes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { QuizJob } from '@/lib/api/studio';

interface QuizProgressIndicatorProps {
  currentQuizJob: QuizJob | null;
}

export const QuizProgressIndicator: React.FC<QuizProgressIndicatorProps> = ({
  currentQuizJob,
}) => {
  if (!currentQuizJob) return null;

  return (
    <div className="p-2 bg-orange-500/5 rounded-md border border-orange-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-orange-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentQuizJob.source_name || 'Generating quiz...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentQuizJob.progress || 'Starting...'}
          </p>
        </div>
      </div>
    </div>
  );
};
