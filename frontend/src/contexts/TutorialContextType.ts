import { createContext } from 'react';

export interface TourStep {
  target: string;
  title: string;
  content: string;
  position: 'top' | 'bottom' | 'left' | 'right';
}

export interface TutorialContextType {
  isOpen: boolean;
  currentStep: number;
  steps: TourStep[];
  isCompleted: boolean;
  startTutorial: () => void;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: number) => void;
  skipTutorial: () => void;
}

export const TutorialContext = createContext<TutorialContextType | undefined>(undefined);
