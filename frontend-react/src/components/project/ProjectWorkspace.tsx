import React, { useState, useRef, useCallback } from 'react';
import { Button } from '../ui/button';
import { SourcesPanel } from '../sources';
import { ChatPanel } from '../chat';
import { StudioPanel, type StudioSignal } from '../studio';
import { ProjectHeader } from './ProjectHeader';
import { CaretLeft, CaretRight, Warning } from '@phosphor-icons/react';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
  type ImperativePanelHandle,
} from '../ui/resizable';

/**
 * ProjectWorkspace Component
 * Educational Note: This is the main workspace view for a project, inspired by NotebookLM.
 *
 * Layout Structure:
 * - Background layer: Contains header and footer disclaimer
 * - Floating panels: Sources, Chat, Studio sit on top with padding and rounded corners
 * - Minimal resize handles that appear on hover
 */

interface ProjectWorkspaceProps {
  project: {
    id: string;
    name: string;
    description: string;
  };
  onBack: () => void;
  onDeleteProject: (projectId: string) => void;
  onRenameProject?: (newName: string) => Promise<void>;
  onSignOut?: () => Promise<void>;
}

export const ProjectWorkspace: React.FC<ProjectWorkspaceProps> = ({
  project,
  onBack,
  onDeleteProject,
  onRenameProject,
  onSignOut,
}) => {
  // Refs for programmatic panel control
  const leftPanelRef = useRef<ImperativePanelHandle>(null);
  const rightPanelRef = useRef<ImperativePanelHandle>(null);

  // State for panel visibility (synced with panel collapse state)
  const [leftPanelOpen, setLeftPanelOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);

  // Costs version counter - increments when costs change (after chat messages or source processing)
  const [costsVersion, setCostsVersion] = useState(0);
  const handleCostsChange = useCallback(() => {
    setCostsVersion(v => v + 1);
  }, []);

  // Sources version counter - increments when sources change to trigger ChatPanel refresh
  // Also triggers cost refresh since source processing uses Claude API
  const [sourcesVersion, setSourcesVersion] = useState(0);
  const handleSourcesChange = useCallback(() => {
    setSourcesVersion(v => v + 1);
    setCostsVersion(v => v + 1); // Source processing also incurs costs
  }, []);

  // Studio signals state - receives signals from ChatPanel, passes to StudioPanel
  // Educational Note: Signals are chat-scoped and activate studio generation options
  const [studioSignals, setStudioSignals] = useState<StudioSignal[]>([]);
  const handleSignalsChange = useCallback((signals: StudioSignal[]) => {
    setStudioSignals(signals);
  }, []);

  // Per-chat source selection state
  // Educational Note: Each chat maintains its own selected sources independently.
  // activeChatId tracks which chat is open; selectedSourceIds tracks that chat's selections.
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);

  const handleActiveChatChange = useCallback((chatId: string | null, sourceIds: string[]) => {
    setActiveChatId(chatId);
    setSelectedSourceIds(sourceIds);
  }, []);

  const handleSelectedSourcesChange = useCallback((newIds: string[]) => {
    setSelectedSourceIds(newIds);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Project Header - sits on background layer */}
      <ProjectHeader
        project={project}
        onBack={onBack}
        onDelete={() => onDeleteProject(project.id)}
        costsVersion={costsVersion}
        onRename={onRenameProject}
        onSignOut={onSignOut}
      />

      {/* Main Content Area - Floating panels over background */}
      <div className="flex-1 flex flex-col px-3 min-h-0">
        {/* Panel Container - bg-background so resize handles blend in as "gaps" */}
        <div className="flex-1 rounded-xl overflow-hidden bg-background min-h-0">
          <ResizablePanelGroup direction="horizontal" className="h-full">
            {/* Left Panel - Sources (Resizable) */}
            <ResizablePanel
              ref={leftPanelRef}
              defaultSize={20}
              minSize={15}
              maxSize={40}
              collapsible
              collapsedSize={4}
              onCollapse={() => setLeftPanelOpen(false)}
              onExpand={() => setLeftPanelOpen(true)}
              className="bg-card overflow-hidden rounded-xl"
            >
              <div className="h-full flex flex-col relative">
                <SourcesPanel
                  projectId={project.id}
                  isCollapsed={!leftPanelOpen}
                  onExpand={() => leftPanelRef.current?.expand()}
                  onSourcesChange={handleSourcesChange}
                  activeChatId={activeChatId}
                  selectedSourceIds={selectedSourceIds}
                  onSelectedSourcesChange={handleSelectedSourcesChange}
                />
                {leftPanelOpen && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => leftPanelRef.current?.collapse()}
                    className="absolute top-2 right-2 z-10 h-8 w-8 hover:bg-muted"
                  >
                    <CaretLeft size={16} />
                  </Button>
                )}
              </div>
            </ResizablePanel>

            <ResizableHandle />

            {/* Center Panel - Chat */}
            <ResizablePanel defaultSize={55} minSize={30} className="bg-card overflow-hidden rounded-xl min-w-0">
              <div className="h-full min-h-0 min-w-0 w-full flex flex-col overflow-hidden">
                <ChatPanel
                  projectId={project.id}
                  projectName={project.name}
                  sourcesVersion={sourcesVersion}
                  onCostsChange={handleCostsChange}
                  onSignalsChange={handleSignalsChange}
                  selectedSourceIds={selectedSourceIds}
                  onActiveChatChange={handleActiveChatChange}
                />
              </div>
            </ResizablePanel>

            <ResizableHandle />

            {/* Right Panel - Studio (Resizable) */}
            <ResizablePanel
              ref={rightPanelRef}
              defaultSize={25}
              minSize={18}
              maxSize={40}
              collapsible
              collapsedSize={4}
              onCollapse={() => setRightPanelOpen(false)}
              onExpand={() => setRightPanelOpen(true)}
              className="bg-card overflow-hidden rounded-xl"
            >
              <div className="h-full flex flex-col relative">
                <StudioPanel
                  projectId={project.id}
                  signals={studioSignals}
                  isCollapsed={!rightPanelOpen}
                  onExpand={() => rightPanelRef.current?.expand()}
                />
                {rightPanelOpen && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => rightPanelRef.current?.collapse()}
                    className="absolute top-2 left-2 z-10 h-8 w-8 hover:bg-muted"
                  >
                    <CaretRight size={16} />
                  </Button>
                )}
              </div>
            </ResizablePanel>
          </ResizablePanelGroup>
        </div>

        {/* Footer Disclaimer - sits on background layer */}
        <div className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Warning size={12} />
          <span>NoobBook can make mistakes. Please verify important information.</span>
        </div>
      </div>
    </div>
  );
};
