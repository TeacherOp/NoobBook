/**
 * StudioContext
 * Educational Note: Provides shared state for Studio panel.
 * Only contains data needed by multiple sections - each section owns its own job state.
 * This eliminates prop drilling while keeping sections isolated.
 */

import React, { createContext, useContext, useMemo, useCallback, useState } from 'react';
import type { StudioSignal, StudioItemId } from './types';
import { generationOptions } from './types';

interface StudioContextValue {
  // Core shared state
  projectId: string;
  signals: StudioSignal[];

  // Memoized Set for O(1) source filtering - replaces O(n^2) nested .some() calls
  validSourceIds: Set<string>;

  // Signal picker state (shared because it's triggered from StudioToolsList)
  pickerOpen: boolean;
  setPickerOpen: (open: boolean) => void;
  selectedItem: StudioItemId | null;
  selectedSignals: StudioSignal[];

  // Generation trigger - called by signal picker after selection
  triggerGeneration: (optionId: StudioItemId, signal: StudioSignal) => void;

  // Register generation handler from sections
  registerGenerationHandler: (itemId: StudioItemId, handler: (signal: StudioSignal) => Promise<void>) => void;

  // Handle generate request from tools list
  handleGenerate: (optionId: StudioItemId, itemSignals: StudioSignal[]) => void;

  // Utility functions
  getItemTitle: (itemId: StudioItemId) => string;
  getItemIcon: (itemId: StudioItemId) => React.ComponentType<{ size?: number; className?: string }> | undefined;
}

const StudioContext = createContext<StudioContextValue | null>(null);

interface StudioProviderProps {
  projectId: string;
  signals: StudioSignal[];
  children: React.ReactNode;
}

export const StudioProvider: React.FC<StudioProviderProps> = ({
  projectId,
  signals,
  children,
}) => {
  // Signal picker state
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<StudioItemId | null>(null);
  const [selectedSignals, setSelectedSignals] = useState<StudioSignal[]>([]);

  // Registry of generation handlers from sections
  const [generationHandlers] = useState<Map<StudioItemId, (signal: StudioSignal) => Promise<void>>>(
    () => new Map()
  );

  // Memoized Set of valid source IDs for O(1) filtering
  // This replaces the O(n^2) pattern: signals.some(s => s.sources.some(src => src.source_id === job.source_id))
  const validSourceIds = useMemo(() => {
    const ids = new Set<string>();
    signals.forEach(signal => {
      // Safely handle signals that may not have sources array
      const sources = signal.sources || [];
      sources.forEach(source => {
        if (source?.source_id) {
          ids.add(source.source_id);
        }
      });
    });
    return ids;
  }, [signals]);

  // Register a generation handler from a section
  const registerGenerationHandler = useCallback((
    itemId: StudioItemId,
    handler: (signal: StudioSignal) => Promise<void>
  ) => {
    generationHandlers.set(itemId, handler);
  }, [generationHandlers]);

  // Get display name for a studio item
  const getItemTitle = useCallback((itemId: StudioItemId): string => {
    const option = generationOptions.find((opt) => opt.id === itemId);
    return option?.title || itemId;
  }, []);

  // Get icon for a studio item
  const getItemIcon = useCallback((itemId: StudioItemId) => {
    const option = generationOptions.find((opt) => opt.id === itemId);
    return option?.icon;
  }, []);

  // Trigger the actual generation workflow
  const triggerGeneration = useCallback(async (optionId: StudioItemId, signal: StudioSignal) => {
    console.log('[StudioContext] triggerGeneration called:', { optionId, signal });
    setPickerOpen(false);

    const handler = generationHandlers.get(optionId);
    console.log('[StudioContext] Handler for', optionId, ':', handler ? 'found' : 'NOT FOUND');
    if (handler) {
      try {
        await handler(signal);
      } catch (error) {
        console.error('[StudioContext] Handler threw error:', error);
      }
    } else {
      console.warn(`No generation handler registered for: ${optionId}`);
    }
  }, [generationHandlers]);

  // Handle generation request from tools list
  // If multiple signals exist for an item, show picker. Otherwise generate directly.
  const handleGenerate = useCallback((optionId: StudioItemId, itemSignals: StudioSignal[]) => {
    console.log('[StudioContext] handleGenerate called:', { optionId, itemSignals });
    if (itemSignals.length === 0) return;

    if (itemSignals.length === 1) {
      // Single signal - generate directly
      console.log('[StudioContext] Triggering generation with signal:', itemSignals[0]);
      triggerGeneration(optionId, itemSignals[0]);
    } else {
      // Multiple signals - show picker
      setSelectedItem(optionId);
      setSelectedSignals(itemSignals);
      setPickerOpen(true);
    }
  }, [triggerGeneration]);

  const value = useMemo<StudioContextValue>(() => ({
    projectId,
    signals,
    validSourceIds,
    pickerOpen,
    setPickerOpen,
    selectedItem,
    selectedSignals,
    triggerGeneration,
    registerGenerationHandler,
    handleGenerate,
    getItemTitle,
    getItemIcon,
  }), [
    projectId,
    signals,
    validSourceIds,
    pickerOpen,
    selectedItem,
    selectedSignals,
    triggerGeneration,
    registerGenerationHandler,
    handleGenerate,
    getItemTitle,
    getItemIcon,
  ]);

  return (
    <StudioContext.Provider value={value}>
      {children}
    </StudioContext.Provider>
  );
};

/**
 * Hook to access studio context
 * Throws if used outside StudioProvider
 */
export const useStudioContext = (): StudioContextValue => {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error('useStudioContext must be used within a StudioProvider');
  }
  return context;
};

/**
 * Hook to filter jobs by valid source IDs
 * Uses the memoized Set for O(1) lookups instead of O(n^2) nested .some() calls
 */
export const useFilteredJobs = <T extends { source_id: string }>(jobs: T[]): T[] => {
  const { validSourceIds } = useStudioContext();

  return useMemo(() => {
    return jobs.filter(job => validSourceIds.has(job.source_id));
  }, [jobs, validSourceIds]);
};
