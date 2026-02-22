import React, { useEffect } from 'react';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../ui/collapsible';
import { Textarea } from '../ui/textarea';
import { ArrowLeft, DotsThreeVertical, Plus, Trash, FolderOpen, Gear, CircleNotch, CurrencyDollar, Brain, CaretDown, CaretRight, PencilSimple, SignOut } from '@phosphor-icons/react';
import { Input } from '../ui/input';
import { chatsAPI, type PromptConfig } from '../../lib/api/chats';
import { projectsAPI, type CostTracking, type MemoryData } from '../../lib/api';
import { useToast, ToastContainer } from '../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('project-header');

/**
 * ProjectHeader Component
 * Educational Note: Header for project workspace with navigation and project actions.
 * Now loads and saves the system prompt using the real API.
 */

interface ProjectHeaderProps {
  project: {
    id: string;
    name: string;
    description?: string;
  };
  onBack: () => void;
  onDelete: () => void;
  costsVersion?: number; // Increment to trigger cost refresh
  onRename?: (newName: string) => Promise<void>;
  onSignOut?: () => Promise<void>;
}

export const ProjectHeader: React.FC<ProjectHeaderProps> = ({
  project,
  onBack,
  onDelete,
  costsVersion,
  onRename,
  onSignOut,
}) => {
  const { toasts, dismissToast, error, success } = useToast();

  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = React.useState(false);

  // Rename dialog state
  const [renameDialogOpen, setRenameDialogOpen] = React.useState(false);
  const [renameValue, setRenameValue] = React.useState(project.name);
  const [renaming, setRenaming] = React.useState(false);

  // Cost tracking state
  const [costs, setCosts] = React.useState<CostTracking | null>(null);

  // Memory state
  const [memoryDialogOpen, setMemoryDialogOpen] = React.useState(false);
  const [memory, setMemory] = React.useState<MemoryData | null>(null);
  const [loadingMemory, setLoadingMemory] = React.useState(false);
  const [editedUserMemory, setEditedUserMemory] = React.useState('');
  const [editedProjectMemory, setEditedProjectMemory] = React.useState('');
  const [savingMemory, setSavingMemory] = React.useState(false);

  // All prompts state (view-only)
  const [allPrompts, setAllPrompts] = React.useState<PromptConfig[]>([]);
  const [loadingPrompts, setLoadingPrompts] = React.useState(false);
  const [expandedPrompts, setExpandedPrompts] = React.useState<Set<string>>(new Set());

  /**
   * Educational Note: Load costs when component mounts.
   */
  useEffect(() => {
    loadCosts();
  }, [project.id]);

  /**
   * Refresh costs when costsVersion changes (triggered after chat messages)
   * Educational Note: Uses version counter pattern for cross-component updates
   */
  useEffect(() => {
    if (costsVersion !== undefined && costsVersion > 0) {
      loadCosts();
    }
  }, [costsVersion]);

  /**
   * Load project cost tracking data
   * Educational Note: Costs are tracked cumulatively in project.json
   */
  const loadCosts = async () => {
    try {
      const response = await projectsAPI.getCosts(project.id);
      if (response.data.success) {
        setCosts(response.data.costs);
      }
    } catch (err) {
      log.error({ err }, 'failed to load costs');
      // Silently fail - costs are not critical
    }
  };

  /**
   * Load memory data (user + project memory)
   * Educational Note: Memory is loaded when user opens the memory dialog.
   * Populates both the display state and editable textarea state.
   */
  const loadMemory = async () => {
    try {
      setLoadingMemory(true);
      const response = await projectsAPI.getMemory(project.id);
      if (response.data.success) {
        const mem = response.data.memory;
        setMemory(mem);
        setEditedUserMemory(mem.user_memory || '');
        setEditedProjectMemory(mem.project_memory || '');
      }
    } catch (err) {
      log.error({ err }, 'failed to load memory');
      error('Failed to load memory');
    } finally {
      setLoadingMemory(false);
    }
  };

  /**
   * Open memory dialog and load memory data
   * Educational Note: Memory is fetched on-demand when dialog opens.
   */
  const handleOpenMemory = () => {
    setMemoryDialogOpen(true);
    loadMemory();
  };

  /**
   * Save edited memory to backend.
   * Only sends fields that actually changed to avoid unnecessary writes.
   */
  const handleSaveMemory = async () => {
    try {
      setSavingMemory(true);
      const updates: { user_memory?: string; project_memory?: string } = {};

      if (editedUserMemory !== (memory?.user_memory || '')) {
        updates.user_memory = editedUserMemory;
      }
      if (editedProjectMemory !== (memory?.project_memory || '')) {
        updates.project_memory = editedProjectMemory;
      }

      await projectsAPI.updateMemory(project.id, updates);

      // Update local state to reflect saved values
      setMemory({
        user_memory: editedUserMemory || null,
        project_memory: editedProjectMemory || null,
      });
      success('Memory saved');
    } catch (err) {
      log.error({ err }, 'failed to save memory');
      error('Failed to save memory');
    } finally {
      setSavingMemory(false);
    }
  };

  /** Check if memory has unsaved edits */
  const memoryIsDirty =
    editedUserMemory !== (memory?.user_memory || '') ||
    editedProjectMemory !== (memory?.project_memory || '');

  /**
   * Load all prompt configurations
   * Educational Note: Prompts are loaded when settings dialog opens.
   */
  const loadAllPrompts = async () => {
    try {
      setLoadingPrompts(true);
      const prompts = await chatsAPI.getAllPrompts();
      setAllPrompts(prompts);
    } catch (err) {
      log.error({ err }, 'failed to load prompts');
      error('Failed to load prompts');
    } finally {
      setLoadingPrompts(false);
    }
  };

  /**
   * Toggle expansion state of a prompt card
   */
  const togglePromptExpanded = (promptName: string) => {
    setExpandedPrompts((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(promptName)) {
        newSet.delete(promptName);
      } else {
        newSet.add(promptName);
      }
      return newSet;
    });
  };

  /**
   * Format prompt name for display
   */
  const formatPromptName = (name: string): string => {
    return name
      .replace(/_/g, ' ')
      .replace(/prompt$/i, '')
      .trim()
      .split(' ')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  /**
   * Get prompt identifier (name or derive from filename)
   */
  const getPromptId = (prompt: PromptConfig): string => {
    return prompt.name || prompt.filename.replace('_prompt.json', '').replace('.json', '');
  };

  /**
   * Format currency for header display (without $ symbol - icon provides it)
   */
  const formatCost = (cost: number): string => {
    if (cost < 0.01) {
      return '0.00';
    }
    return cost.toFixed(2);
  };

  /**
   * Format currency for tooltip with $ symbol
   */
  const formatCostWithSymbol = (cost: number): string => {
    if (cost < 0.01) {
      return '$0.00';
    }
    return `$${cost.toFixed(2)}`;
  };

  /**
   * Format token count with K suffix for thousands
   */
  const formatTokens = (tokens: number): string => {
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  const handleRename = async () => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === project.name || !onRename) return;
    try {
      setRenaming(true);
      await onRename(trimmed);
      setRenameDialogOpen(false);
    } catch (err) {
      log.error({ err }, 'failed to rename project');
      error('Failed to rename project');
    } finally {
      setRenaming(false);
    }
  };

  const handleNewProject = () => {
    // Navigate back to project list
    onBack();
  };

  const handleOpenSettings = () => {
    setSettingsDialogOpen(true);
    // Only load prompts if not already loaded
    if (allPrompts.length === 0) {
      loadAllPrompts();
    }
  };

  return (
    <div className="h-14 flex items-center justify-between px-4 bg-background">
      {/* Left side - Back button and project name */}
      <div className="flex items-center gap-3">
        <Button
          variant="soft"
          size="icon"
          onClick={onBack}
          className="h-8 w-8"
        >
          <ArrowLeft size={16} />
        </Button>

        <div className="flex items-center gap-2">
          <FolderOpen size={20} className="text-muted-foreground" />
          <h1 className="text-lg font-semibold">{project.name}</h1>
        </div>

        {/* Cost Display with Hover Breakdown */}
        {costs && costs.total_cost > 0 && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1.5 px-2 py-1 bg-muted/50 rounded-md cursor-default">
                  <CurrencyDollar size={14} className="text-muted-foreground" />
                  <span className="text-sm text-muted-foreground font-medium">
                    {formatCost(costs.total_cost)}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="p-3">
                <div className="space-y-2 text-xs">
                  <p className="font-semibold text-sm mb-2">API Usage Breakdown</p>

                  {/* Sonnet breakdown */}
                  {(costs.by_model.sonnet.input_tokens > 0 || costs.by_model.sonnet.output_tokens > 0) && (
                    <div className="space-y-1">
                      <p className="font-medium">Sonnet</p>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                        <span>Input:</span>
                        <span>{formatTokens(costs.by_model.sonnet.input_tokens)} tokens</span>
                        <span>Output:</span>
                        <span>{formatTokens(costs.by_model.sonnet.output_tokens)} tokens</span>
                        <span>Cost:</span>
                        <span className="font-medium text-foreground">{formatCostWithSymbol(costs.by_model.sonnet.cost)}</span>
                      </div>
                    </div>
                  )}

                  {/* Haiku breakdown */}
                  {(costs.by_model.haiku.input_tokens > 0 || costs.by_model.haiku.output_tokens > 0) && (
                    <div className="space-y-1">
                      <p className="font-medium">Haiku</p>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                        <span>Input:</span>
                        <span>{formatTokens(costs.by_model.haiku.input_tokens)} tokens</span>
                        <span>Output:</span>
                        <span>{formatTokens(costs.by_model.haiku.output_tokens)} tokens</span>
                        <span>Cost:</span>
                        <span className="font-medium text-foreground">{formatCostWithSymbol(costs.by_model.haiku.cost)}</span>
                      </div>
                    </div>
                  )}

                  <div className="border-t pt-2 mt-2">
                    <div className="flex justify-between font-medium">
                      <span>Total:</span>
                      <span>{formatCostWithSymbol(costs.total_cost)}</span>
                    </div>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="soft"
          size="sm"
          onClick={handleOpenMemory}
          className="gap-2"
        >
          <Brain size={16} />
          Memory
        </Button>

        <Button
          variant="soft"
          size="sm"
          onClick={handleOpenSettings}
          className="gap-2"
        >
          <Gear size={16} />
          Project Settings
        </Button>

        <Button
          variant="soft"
          size="sm"
          onClick={handleNewProject}
          className="gap-2"
        >
          <Plus size={16} />
          New Project
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="soft" size="icon" className="h-8 w-8">
              <DotsThreeVertical size={16} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => {
              setRenameValue(project.name);
              setRenameDialogOpen(true);
            }}>
              <PencilSimple size={16} className="mr-2" />
              Rename Project
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => setDeleteDialogOpen(true)}
            >
              <Trash size={16} className="mr-2" />
              Delete Project
            </DropdownMenuItem>
            {onSignOut && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onSignOut}>
                  <SignOut size={16} className="mr-2" />
                  Sign out
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Are you absolutely sure?</DialogTitle>
            <DialogDescription>
              This will permanently delete "{project.name}" and all of its data.
              This action cannot be undone. All sources, chats, and generated content
              will be lost forever.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="soft"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                onDelete();
                setDeleteDialogOpen(false);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename Project Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={(open) => {
        if (!renaming) setRenameDialogOpen(open);
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Rename Project</DialogTitle>
            <DialogDescription>
              Enter a new name for this project.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename();
              }}
              placeholder="Project name"
              disabled={renaming}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="soft"
              onClick={() => setRenameDialogOpen(false)}
              disabled={renaming}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRename}
              disabled={renaming || !renameValue.trim() || renameValue.trim() === project.name}
            >
              {renaming ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Project Settings Dialog */}
      <Dialog open={settingsDialogOpen} onOpenChange={setSettingsDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Project Settings</DialogTitle>
            <DialogDescription>
              Configure settings for "{project.name}"
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* All Prompts Section (View Only) */}
            <div className="space-y-3">
              <div>
                <Label>All System Prompts</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  View all prompt configurations used by the application (read-only)
                </p>
              </div>

              {loadingPrompts ? (
                    <div className="flex items-center justify-center py-4">
                      <CircleNotch size={20} className="animate-spin text-muted-foreground" />
                      <span className="ml-2 text-sm text-muted-foreground">Loading prompts...</span>
                    </div>
                  ) : allPrompts.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic py-4">
                      No prompts found in the prompts folder.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {allPrompts.map((prompt) => {
                        const promptId = getPromptId(prompt);
                        return (
                        <Collapsible
                          key={prompt.filename}
                          open={expandedPrompts.has(promptId)}
                          onOpenChange={() => togglePromptExpanded(promptId)}
                        >
                          <div className="border rounded-lg">
                            <CollapsibleTrigger asChild>
                              <button className="w-full p-3 hover:bg-muted/50 transition-colors text-left">
                                <div className="flex items-start justify-between gap-3">
                                  {/* Left: Caret + Title + Filename below */}
                                  <div className="flex items-start gap-3 min-w-0">
                                    <div className="pt-0.5">
                                      {expandedPrompts.has(promptId) ? (
                                        <CaretDown size={16} className="text-muted-foreground" />
                                      ) : (
                                        <CaretRight size={16} className="text-muted-foreground" />
                                      )}
                                    </div>
                                    <div className="min-w-0">
                                      <div className="font-medium">{formatPromptName(promptId)}</div>
                                      <div className="text-xs text-muted-foreground">
                                        ({prompt.filename})
                                      </div>
                                    </div>
                                  </div>
                                  {/* Right: Model + Temp + Max Tokens */}
                                  <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0 pt-0.5">
                                    {prompt.model && (
                                      <span>{prompt.model}</span>
                                    )}
                                    {prompt.temperature !== undefined && (
                                      <span>temp: {prompt.temperature}</span>
                                    )}
                                    {prompt.max_tokens !== undefined && (
                                      <span>max: {prompt.max_tokens.toLocaleString()}</span>
                                    )}
                                  </div>
                                </div>
                              </button>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="border-t p-3 space-y-4 bg-muted/30">
                                {/* Description */}
                                {prompt.description && (
                                  <div>
                                    <Label className="text-xs">Description</Label>
                                    <p className="text-sm text-muted-foreground mt-1">
                                      {prompt.description}
                                    </p>
                                  </div>
                                )}

                                {/* System Prompt */}
                                <div>
                                  <Label className="text-xs">System Prompt</Label>
                                  <div className="mt-1 p-2 bg-background rounded border max-h-48 overflow-y-auto">
                                    <pre className="text-xs font-mono whitespace-pre-wrap">
                                      {prompt.system_prompt}
                                    </pre>
                                  </div>
                                </div>

                                {/* User Message (if present) */}
                                {(prompt.user_message || prompt.user_message_template) && (
                                  <div>
                                    <Label className="text-xs">
                                      {prompt.user_message_template ? 'User Message Template' : 'User Message'}
                                    </Label>
                                    <div className="mt-1 p-2 bg-background rounded border max-h-32 overflow-y-auto">
                                      <pre className="text-xs font-mono whitespace-pre-wrap">
                                        {prompt.user_message || prompt.user_message_template}
                                      </pre>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </CollapsibleContent>
                          </div>
                        </Collapsible>
                      );
                      })}
                    </div>
                  )}
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="soft"
              onClick={() => setSettingsDialogOpen(false)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Memory Dialog */}
      <Dialog open={memoryDialogOpen} onOpenChange={(open) => {
        if (!savingMemory) setMemoryDialogOpen(open);
      }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Brain size={20} />
              Memory
            </DialogTitle>
            <DialogDescription>
              Edit what the AI remembers about you and this project
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {loadingMemory ? (
              <div className="flex items-center justify-center py-8">
                <CircleNotch size={24} className="animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">Loading memory...</span>
              </div>
            ) : (
              <>
                {/* User Memory Section */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>User Memory</Label>
                    {editedUserMemory && (
                      <button
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors border rounded px-2 py-0.5"
                        onClick={() => setEditedUserMemory('')}
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Persists across all your projects
                  </p>
                  <Textarea
                    value={editedUserMemory}
                    onChange={(e) => setEditedUserMemory(e.target.value)}
                    placeholder="The AI will remember important details about you as you chat, or you can add them here."
                    className="min-h-[100px] resize-y"
                    disabled={savingMemory}
                  />
                </div>

                {/* Project Memory Section */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Project Memory</Label>
                    {editedProjectMemory && (
                      <button
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors border rounded px-2 py-0.5"
                        onClick={() => setEditedProjectMemory('')}
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Specific to "{project.name}"
                  </p>
                  <Textarea
                    value={editedProjectMemory}
                    onChange={(e) => setEditedProjectMemory(e.target.value)}
                    placeholder="The AI will remember project-specific details as you chat, or you can add them here."
                    className="min-h-[100px] resize-y"
                    disabled={savingMemory}
                  />
                </div>
              </>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="soft"
              onClick={() => setMemoryDialogOpen(false)}
              disabled={savingMemory}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveMemory}
              disabled={savingMemory || !memoryIsDirty}
            >
              {savingMemory ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
