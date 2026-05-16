import React, { useState, useCallback } from 'react';
import { TutorialContext, type TourStep } from './TutorialContextType';

const STORAGE_KEY = 'noobbook_onboarding_completed';
const SEEN_KEY = 'noobbook_onboarding_seen';

// 5-step first-run tour (Sno 52 / GH #255). Targets reference `data-tour`
// attributes attached to the corresponding panel / header element.
const defaultSteps: TourStep[] = [
  {
    target: 'welcome-intro',
    title: 'Welcome to NoobBook',
    content:
      "NoobBook is your AI-powered workspace — upload sources, chat with them, and generate content like presentations, blogs, and reports. Here's a quick 5-step tour of the three panels you'll work in.",
    position: 'bottom',
  },
  {
    target: 'sources-panel',
    title: 'Sources — your content lives here',
    content:
      'Upload PDFs, DOCX, PPTX, XLSX, images, and audio; paste text or URLs; or import from Google Drive. The AI processes each source so chat and Studio can search across them.',
    position: 'right',
  },
  {
    target: 'chat-panel',
    title: 'Chat — ask anything about your sources',
    content:
      'Get cited answers grounded in your documents. Hit the microphone for voice input, drag images into the box to attach them, and use the "Save as insight" button on any reply to pin it.',
    position: 'left',
  },
  {
    target: 'studio-panel',
    title: 'Studio — turn sources into deliverables',
    content:
      'Generate presentations, blogs, social posts, infographics, components, wireframes, business reports, and more. Saved Insights from chat also live here for quick reuse.',
    position: 'left',
  },
  {
    target: 'memory-btn',
    title: 'Memory & Settings — make it yours',
    content:
      'Memory teaches the AI about you and this project so answers stay on-brand. Project Settings lets you tweak the system prompt, rename, or share. You can replay this tour anytime from there.',
    position: 'bottom',
  },
];

const getInitialTutorialState = () => {
  const completed = localStorage.getItem(STORAGE_KEY);
  const seen = localStorage.getItem(SEEN_KEY);
  // Auto-open only if the tutorial has never been shown before.
  // "Seen" is now set when the tutorial component actually renders.
  const shouldAutoOpen = !completed && !seen;
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
