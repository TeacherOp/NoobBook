/**
 * QuizListItem Component
 * Educational Note: Renders saved quizzes in the Generated Content list.
 */

import React from 'react';
import { Exam } from '@phosphor-icons/react';
import type { QuizJob } from '@/lib/api/studio';

interface QuizListItemProps {
  job: QuizJob;
  onClick: () => void;
}

export const QuizListItem: React.FC<QuizListItemProps> = ({ job, onClick }) => {
  return (
    <div
      className="flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-orange-500/10 rounded-md flex-shrink-0">
        <Exam size={16} className="text-orange-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">{job.source_name}</p>
      </div>
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.question_count}
      </span>
    </div>
  );
};
