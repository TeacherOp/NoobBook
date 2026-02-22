/**
 * QuizViewerModal Component
 * Educational Note: Modal for viewing interactive quiz questions.
 * Uses QuizViewer component for question display and answer checking.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Exam } from '@phosphor-icons/react';
import { QuizViewer } from './QuizViewer';
import type { QuizJob } from '@/lib/api/studio';

interface QuizViewerModalProps {
  viewingQuizJob: QuizJob | null;
  onClose: () => void;
}

export const QuizViewerModal: React.FC<QuizViewerModalProps> = ({
  viewingQuizJob,
  onClose,
}) => {
  return (
    <Dialog open={viewingQuizJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-3xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Exam size={20} className="text-orange-600" />
            Quiz - {viewingQuizJob?.source_name}
          </DialogTitle>
          {viewingQuizJob?.topic_summary && (
            <DialogDescription>
              {viewingQuizJob.topic_summary}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Quiz Viewer */}
        <div className="flex-1 min-h-0">
          {viewingQuizJob && (
            <QuizViewer
              questions={viewingQuizJob.questions}
              topicSummary={viewingQuizJob.topic_summary}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
