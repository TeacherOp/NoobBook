import React, { useState, useCallback } from 'react';
import { TutorialContext, type TourStep } from './TutorialContextType';

const STORAGE_KEY = 'noobbook_onboarding_completed';
const SEEN_KEY = 'noobbook_onboarding_seen';

const defaultSteps: TourStep[] = [
  {
    target: 'welcome-intro',
    title: 'Welcome to NoobBook!',
    content: 'NoobBook is your AI-powered workspace. Upload documents, chat with them, and generate content — all in one place. Let us give you a quick tour!',
    position: 'bottom',
  },
  {
    target: 'sources-panel',
    title: 'Your Sources - The Foundation',
    content: 'All your documents, URLs, audio files, and content live here. Add sources first - the AI needs content to work with! Sources are processed with AI to make them searchable.',
    position: 'right',
  },
  {
    target: 'add-sources-btn',
    title: 'Add Sources - 6 Ways to Import',
    content: 'Click here to add content: (1) Upload files - PDF, DOCX, PPTX, images, audio (2) Add URLs (3) Paste text (4) Google Drive (5) AI Research - give a topic and let AI research it (6) Database connections',
    position: 'bottom',
  },
  {
    target: 'chat-panel',
    title: 'Chat with Your Sources',
    content: 'Ask questions about your sources and get AI-powered answers. The AI searches through all your documents to find relevant information. Click the microphone for voice input!',
    position: 'left',
  },
  {
    target: 'studio-panel',
    title: 'Studio - Generate Content',
    content: 'Transform your sources into: Learning (Quiz, Flash Cards, Audio Overview, Mind Map), Business (Reports, Marketing, PRD, Presentation), Content (Blog, Social Posts, Website, Email). Select sources first!',
    position: 'left',
  },
  {
    target: 'memory-btn',
    title: 'Personalize with Memory',
    content: 'Teach the AI about you! Add your background, preferences, and project context. User Memory applies to all projects, Project Memory is specific to this project. The AI learns from chats too!',
    position: 'bottom',
  },
  {
    target: 'cost-display',
    title: 'Track Your Costs',
    content: 'Monitor your API usage in real-time. Hover over the cost display to see detailed breakdown by model (Claude Sonnet/Haiku) with input/output token counts.',
    position: 'bottom',
  },
  {
    target: 'settings-btn',
    title: 'Project Settings',
    content: 'Customize how the AI behaves. View system prompts, rename your project, or delete it. Need help? Click "Learn about NoobBook" here for a complete feature tour!',
    position: 'bottom',
  },
];

const getInitialTutorialState = () => {
  const completed = localStorage.getItem(STORAGE_KEY);
  const seen = localStorage.getItem(SEEN_KEY);
  // Auto-open only if the tutorial has NEVER been shown before (first-ever visit)
  const shouldAutoOpen = !completed && !seen;
  if (shouldAutoOpen) {
    // Mark as seen immediately so it won't auto-open on the next project
    localStorage.setItem(SEEN_KEY, 'true');
  }
  return {
    isOpen: shouldAutoOpen,
    isCompleted: !!completed,
  };
};

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [initialState] = useState(getInitialTutorialState);
  const [isOpen, setIsOpen] = useState(initialState.isOpen);
  const [currentStep, setCurrentStep] = useState(0);
  const [steps] = useState<TourStep[]>(defaultSteps);
  const [isCompleted, setIsCompleted] = useState(initialState.isCompleted);

  const startTutorial = useCallback(() => {
    setIsOpen(true);
    setCurrentStep(0);
    setIsCompleted(false);
  }, []);

  const nextStep = useCallback(() => {
    setCurrentStep((prev) => {
      if (prev >= steps.length - 1) {
        setIsOpen(false);
        localStorage.setItem(STORAGE_KEY, 'true');
        setIsCompleted(true);
        return prev;
      }
      return prev + 1;
    });
  }, [steps.length]);

  const prevStep = useCallback(() => {
    setCurrentStep((prev) => Math.max(0, prev - 1));
  }, []);

  const goToStep = useCallback((step: number) => {
    setCurrentStep(step);
  }, []);

  const skipTutorial = useCallback(() => {
    setIsOpen(false);
    localStorage.setItem(STORAGE_KEY, 'true');
    setIsCompleted(true);
  }, []);

  return (
    <TutorialContext.Provider
      value={{
        isOpen,
        currentStep,
        steps,
        isCompleted,
        startTutorial,
        nextStep,
        prevStep,
        goToStep,
        skipTutorial,
      }}
    >
      {children}
    </TutorialContext.Provider>
  );
};
