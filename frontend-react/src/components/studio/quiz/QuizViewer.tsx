/**
 * Quiz Viewer Component
 * Educational Note: Interactive quiz component for testing knowledge.
 *
 * Features:
 * - Single and multi-select question support
 * - Optional hints for questions
 * - Answer validation with explanations
 * - Progress tracking and scoring
 * - Navigation between questions
 */

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  CaretLeft,
  CaretRight,
  Check,
  X,
  Lightbulb,
  ListChecks,
  ArrowClockwise,
} from '@phosphor-icons/react';
import type { QuizQuestion } from '@/lib/api/studio';

interface QuizViewerProps {
  questions: QuizQuestion[];
  topicSummary?: string | null;
}

interface QuestionState {
  selectedAnswers: string[];
  isSubmitted: boolean;
  isCorrect: boolean;
  showHint: boolean;
}

export function QuizViewer({ questions, topicSummary }: QuizViewerProps) {
  // Current question index
  const [currentIndex, setCurrentIndex] = useState(0);

  // Track state for each question
  const [questionStates, setQuestionStates] = useState<Record<string, QuestionState>>(() => {
    const initial: Record<string, QuestionState> = {};
    questions.forEach((q) => {
      initial[q.id] = {
        selectedAnswers: [],
        isSubmitted: false,
        isCorrect: false,
        showHint: false,
      };
    });
    return initial;
  });

  // Show summary view at the end
  const [showSummary, setShowSummary] = useState(false);

  const currentQuestion = questions[currentIndex];
  const currentState = questionStates[currentQuestion?.id] || {
    selectedAnswers: [],
    isSubmitted: false,
    isCorrect: false,
    showHint: false,
  };

  // Calculate score
  const answeredQuestions = Object.values(questionStates).filter((s) => s.isSubmitted);
  const correctAnswers = answeredQuestions.filter((s) => s.isCorrect).length;

  // Toggle answer selection
  const toggleAnswer = useCallback(
    (optionId: string) => {
      if (currentState.isSubmitted) return;

      setQuestionStates((prev) => {
        const current = prev[currentQuestion.id];
        let newSelected: string[];

        if (currentQuestion.is_multi_select) {
          // Multi-select: toggle the option
          if (current.selectedAnswers.includes(optionId)) {
            newSelected = current.selectedAnswers.filter((id) => id !== optionId);
          } else {
            newSelected = [...current.selectedAnswers, optionId];
          }
        } else {
          // Single-select: replace selection
          newSelected = [optionId];
        }

        return {
          ...prev,
          [currentQuestion.id]: {
            ...current,
            selectedAnswers: newSelected,
          },
        };
      });
    },
    [currentQuestion, currentState.isSubmitted]
  );

  // Submit answer
  const submitAnswer = useCallback(() => {
    if (currentState.selectedAnswers.length === 0) return;

    const correct = currentQuestion.correct_answers;
    const selected = currentState.selectedAnswers;

    // Check if answers match (order doesn't matter)
    const isCorrect =
      correct.length === selected.length &&
      correct.every((a) => selected.includes(a)) &&
      selected.every((a) => correct.includes(a));

    setQuestionStates((prev) => ({
      ...prev,
      [currentQuestion.id]: {
        ...prev[currentQuestion.id],
        isSubmitted: true,
        isCorrect,
      },
    }));
  }, [currentQuestion, currentState.selectedAnswers]);

  // Toggle hint visibility
  const toggleHint = useCallback(() => {
    setQuestionStates((prev) => ({
      ...prev,
      [currentQuestion.id]: {
        ...prev[currentQuestion.id],
        showHint: !prev[currentQuestion.id].showHint,
      },
    }));
  }, [currentQuestion]);

  // Navigation
  const goToNext = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      setShowSummary(true);
    }
  }, [currentIndex, questions.length]);

  const goToPrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  }, [currentIndex]);

  // Reset quiz
  const resetQuiz = useCallback(() => {
    const initial: Record<string, QuestionState> = {};
    questions.forEach((q) => {
      initial[q.id] = {
        selectedAnswers: [],
        isSubmitted: false,
        isCorrect: false,
        showHint: false,
      };
    });
    setQuestionStates(initial);
    setCurrentIndex(0);
    setShowSummary(false);
  }, [questions]);

  if (questions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No quiz questions available
      </div>
    );
  }

  // Summary view
  if (showSummary) {
    const percentage = Math.round((correctAnswers / questions.length) * 100);

    return (
      <div className="w-full h-full flex flex-col">
        {/* Header */}
        <div className="px-4 py-3 bg-muted/30 border-b flex-shrink-0">
          <h3 className="font-semibold text-lg">Quiz Complete</h3>
          {topicSummary && (
            <p className="text-sm text-muted-foreground mt-1">{topicSummary}</p>
          )}
        </div>

        {/* Score */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-lg mx-auto">
            {/* Score Card */}
            <div className="bg-muted/50 rounded-lg p-6 text-center mb-6">
              <div className="text-5xl font-bold mb-2">
                {correctAnswers}/{questions.length}
              </div>
              <div className="text-lg text-muted-foreground">
                {percentage}% Correct
              </div>
              <div className="mt-4">
                {percentage >= 80 ? (
                  <span className="text-green-600 font-medium">Excellent work!</span>
                ) : percentage >= 60 ? (
                  <span className="text-yellow-600 font-medium">Good job, keep practicing!</span>
                ) : (
                  <span className="text-orange-600 font-medium">
                    Review the material and try again
                  </span>
                )}
              </div>
            </div>

            {/* Question Review */}
            <div className="space-y-3">
              <h4 className="font-medium text-sm text-muted-foreground mb-2">
                Question Review
              </h4>
              {questions.map((q, idx) => {
                const state = questionStates[q.id];
                return (
                  <button
                    key={q.id}
                    onClick={() => {
                      setCurrentIndex(idx);
                      setShowSummary(false);
                    }}
                    className={cn(
                      'w-full p-3 rounded-lg border text-left transition-colors',
                      'hover:bg-muted/50',
                      state?.isSubmitted
                        ? state.isCorrect
                          ? 'border-green-500/50 bg-green-500/5'
                          : 'border-red-500/50 bg-red-500/5'
                        : 'border-muted-foreground/20'
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                        {idx + 1}
                      </span>
                      <span className="flex-1 text-sm truncate">{q.question}</span>
                      {state?.isSubmitted && (
                        <span className="flex-shrink-0">
                          {state.isCorrect ? (
                            <Check size={18} className="text-green-600" weight="bold" />
                          ) : (
                            <X size={18} className="text-red-600" weight="bold" />
                          )}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Retry Button */}
            <div className="mt-6 flex justify-center">
              <Button onClick={resetQuiz} variant="soft" className="gap-2">
                <ArrowClockwise size={18} />
                Retake Quiz
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Question view
  return (
    <div className="w-full h-full flex flex-col">
      {/* Header with progress */}
      <div className="px-4 py-3 bg-muted/30 border-b flex items-center justify-between gap-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <ListChecks size={20} className="text-muted-foreground" />
          <span className="font-medium">
            Question {currentIndex + 1} of {questions.length}
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            Score: {correctAnswers}/{answeredQuestions.length}
          </span>
          {/* Progress bar */}
          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Question content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          {/* Question type badge */}
          {currentQuestion.is_multi_select && (
            <div className="mb-3">
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                Select all that apply
              </span>
            </div>
          )}

          {/* Question text */}
          <h3 className="text-lg font-medium mb-6">{currentQuestion.question}</h3>

          {/* Options */}
          <div className="space-y-3 mb-6">
            {currentQuestion.options.map((option) => {
              const isSelected = currentState.selectedAnswers.includes(option.id);
              const isCorrectAnswer = currentQuestion.correct_answers.includes(option.id);
              const showResult = currentState.isSubmitted;

              return (
                <button
                  key={option.id}
                  onClick={() => toggleAnswer(option.id)}
                  disabled={currentState.isSubmitted}
                  className={cn(
                    'w-full p-4 rounded-lg border text-left transition-all',
                    'flex items-center gap-3',
                    !showResult && isSelected
                      ? 'border-primary bg-primary/5'
                      : !showResult
                        ? 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/50'
                        : '',
                    showResult && isCorrectAnswer && 'border-green-500 bg-green-500/10',
                    showResult && isSelected && !isCorrectAnswer && 'border-red-500 bg-red-500/10',
                    showResult && !isSelected && !isCorrectAnswer && 'border-muted-foreground/20 opacity-60'
                  )}
                >
                  {/* Checkbox/Radio indicator */}
                  <span
                    className={cn(
                      'flex-shrink-0 w-5 h-5 rounded flex items-center justify-center border-2',
                      currentQuestion.is_multi_select ? 'rounded' : 'rounded-full',
                      !showResult && isSelected
                        ? 'border-primary bg-primary text-white'
                        : !showResult
                          ? 'border-muted-foreground/40'
                          : '',
                      showResult && isCorrectAnswer && 'border-green-500 bg-green-500 text-white',
                      showResult && isSelected && !isCorrectAnswer && 'border-red-500 bg-red-500 text-white'
                    )}
                  >
                    {((showResult && isCorrectAnswer) || (!showResult && isSelected)) && (
                      <Check size={12} weight="bold" />
                    )}
                    {showResult && isSelected && !isCorrectAnswer && (
                      <X size={12} weight="bold" />
                    )}
                  </span>

                  {/* Option text */}
                  <span className="flex-1">{option.text}</span>
                </button>
              );
            })}
          </div>

          {/* Hint */}
          {currentQuestion.hint && !currentState.isSubmitted && (
            <div className="mb-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleHint}
                className="gap-2 text-muted-foreground"
              >
                <Lightbulb size={16} />
                {currentState.showHint ? 'Hide Hint' : 'Show Hint'}
              </Button>
              {currentState.showHint && (
                <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
                  {currentQuestion.hint}
                </div>
              )}
            </div>
          )}

          {/* Explanation (after submit) */}
          {currentState.isSubmitted && (
            <div
              className={cn(
                'p-4 rounded-lg border mb-6',
                currentState.isCorrect
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                {currentState.isCorrect ? (
                  <>
                    <Check size={20} className="text-green-600" weight="bold" />
                    <span className="font-medium text-green-700">Correct!</span>
                  </>
                ) : (
                  <>
                    <X size={20} className="text-red-600" weight="bold" />
                    <span className="font-medium text-red-700">Incorrect</span>
                  </>
                )}
              </div>
              <p className="text-sm text-muted-foreground">{currentQuestion.explanation}</p>
            </div>
          )}

          {/* Submit button */}
          {!currentState.isSubmitted && (
            <Button
              onClick={submitAnswer}
              disabled={currentState.selectedAnswers.length === 0}
              className="w-full"
            >
              Check Answer
            </Button>
          )}
        </div>
      </div>

      {/* Navigation footer */}
      <div className="px-4 py-3 bg-muted/30 border-t flex items-center justify-between gap-4 flex-shrink-0">
        <Button
          variant="soft"
          size="sm"
          onClick={goToPrev}
          disabled={currentIndex === 0}
          className="gap-1"
        >
          <CaretLeft size={16} />
          Previous
        </Button>

        <Button
          variant="soft"
          size="sm"
          onClick={() => setShowSummary(true)}
          className="text-muted-foreground"
        >
          View Summary
        </Button>

        <Button
          variant={currentState.isSubmitted ? 'default' : 'outline'}
          size="sm"
          onClick={goToNext}
          className="gap-1"
        >
          {currentIndex === questions.length - 1 ? 'Finish' : 'Next'}
          <CaretRight size={16} />
        </Button>
      </div>
    </div>
  );
}
