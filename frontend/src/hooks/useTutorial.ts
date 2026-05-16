import { useContext } from 'react';
import { TutorialContext } from '../contexts/TutorialContextType';

export const useTutorial = () => {
  const context = useContext(TutorialContext);
  if (!context) {
    throw new Error('useTutorial must be used within a TutorialProvider');
  }
  return context;
};
