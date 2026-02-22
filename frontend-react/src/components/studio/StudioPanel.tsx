/**
 * StudioPanel Component
 * Educational Note: Layout-only orchestrator for the Studio panel.
 * All feature state is owned by individual sections via StudioContext.
 * This component only handles layout - no hooks, no props drilling.
 *
 * Architecture:
 * - StudioProvider: Shared context (projectId, signals, picker state)
 * - StudioToolsList: Generation tool buttons
 * - StudioSections: Self-contained feature sections (each owns its state)
 * - StudioSignalPicker: Modal for selecting from multiple signals
 */

import React from 'react';
import { StudioHeader } from './StudioHeader';
import { StudioToolsList } from './StudioToolsList';
import { StudioCollapsedView } from './StudioCollapsedView';
import { StudioSignalPicker } from './StudioSignalPicker';
import { StudioProvider, useStudioContext } from './StudioContext';
import { StudioSections } from './sections/StudioSections';
import { ScrollArea } from '../ui/scroll-area';
import type { StudioSignal } from './types';

interface StudioPanelProps {
  projectId: string;
  signals: StudioSignal[];
  isCollapsed?: boolean;
  onExpand?: () => void;
}

/**
 * Inner panel content - uses context
 */
const StudioPanelContent: React.FC = () => {
  const {
    pickerOpen,
    setPickerOpen,
    selectedItem,
    selectedSignals,
    triggerGeneration,
    getItemTitle,
    getItemIcon,
  } = useStudioContext();

  return (
    <div className="flex flex-col h-full">
      <StudioHeader />

      {/* TOP HALF: Generation Tools */}
      <div className="flex-1 min-h-0 border-b flex flex-col">
        <StudioToolsList />
      </div>

      {/* BOTTOM HALF: Generated Outputs */}
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="px-3 py-2 border-b">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Generated Content
          </h3>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-3 space-y-2">
            {/* All sections render here - each manages its own state */}
            <StudioSections />
          </div>
        </ScrollArea>
      </div>

      {/* Signal Picker Dialog */}
      <StudioSignalPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        selectedItem={selectedItem}
        selectedSignals={selectedSignals}
        onSelectSignal={triggerGeneration}
        getItemTitle={getItemTitle}
        getItemIcon={getItemIcon}
      />
    </div>
  );
};

/**
 * Main StudioPanel - provides context and handles collapsed state
 */
export const StudioPanel: React.FC<StudioPanelProps> = ({
  projectId,
  signals,
  isCollapsed,
  onExpand,
}) => {
  // Collapsed view doesn't need the full context
  if (isCollapsed) {
    return (
      <StudioProvider projectId={projectId} signals={signals}>
        <CollapsedViewWrapper onExpand={onExpand!} />
      </StudioProvider>
    );
  }

  return (
    <StudioProvider projectId={projectId} signals={signals}>
      <StudioPanelContent />
    </StudioProvider>
  );
};

/**
 * Wrapper for collapsed view that uses context
 */
const CollapsedViewWrapper: React.FC<{ onExpand: () => void }> = ({ onExpand }) => {
  const { signals, handleGenerate } = useStudioContext();

  return (
    <StudioCollapsedView
      signals={signals}
      onExpand={onExpand}
      onGenerate={handleGenerate}
    />
  );
};
