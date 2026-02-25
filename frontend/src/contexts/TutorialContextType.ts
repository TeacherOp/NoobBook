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
  currentTarget: string | null;
  startTutorial: () => void;
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: number) => void;
  endTutorial: () => void;
  skipTutorial: () => void;
}

export const TutorialContext = createContext<TutorialContextType | undefined>(undefined);
