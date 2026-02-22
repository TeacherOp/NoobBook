/**
 * StudioCollapsedView Component
 * Educational Note: Collapsed icon bar view for the Studio panel.
 * Shows icons for each studio item with active indicators.
 */

import React from 'react';
import { ScrollArea } from '../ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import { MagicWand, CaretLeft } from '@phosphor-icons/react';
import { generationOptions, type StudioSignal, type StudioItemId } from './types';

interface StudioCollapsedViewProps {
  signals: StudioSignal[];
  onExpand: () => void;
  onGenerate: (optionId: StudioItemId, itemSignals: StudioSignal[]) => void;
}

export const StudioCollapsedView: React.FC<StudioCollapsedViewProps> = ({
  signals,
  onExpand,
  onGenerate,
}) => {
  return (
    <TooltipProvider delayDuration={100}>
      <div className="h-full flex flex-col items-center py-3 bg-card">
        {/* Studio header icon */}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={onExpand}
              className="p-2 rounded-lg hover:bg-muted transition-colors mb-2"
            >
              <MagicWand size={20} className="text-primary" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Studio</p>
          </TooltipContent>
        </Tooltip>

        {/* Expand button */}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={onExpand}
              className="p-1.5 rounded-lg hover:bg-muted transition-colors mb-3"
            >
              <CaretLeft size={14} className="text-muted-foreground" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="left">
            <p>Expand panel</p>
          </TooltipContent>
        </Tooltip>

        {/* Action icons - only show active items */}
        <ScrollArea className="flex-1 w-full">
          <div className="flex flex-col items-center gap-1 px-1">
            {generationOptions.map((option) => {
              const itemSignals = signals.filter((s) => s.studio_item === option.id);
              const isActive = itemSignals.length > 0;
              const IconComponent = option.icon;

              return (
                <Tooltip key={option.id}>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => isActive && onGenerate(option.id, itemSignals)}
                      className={`p-2 rounded-lg transition-colors w-full flex justify-center relative ${
                        isActive
                          ? 'hover:bg-muted'
                          : 'opacity-30 cursor-default'
                      }`}
                      disabled={!isActive}
                    >
                      <IconComponent
                        size={18}
                        className={isActive ? 'text-primary' : 'text-muted-foreground'}
                      />
                      {/* Active indicator */}
                      {isActive && (
                        <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-primary rounded-full" />
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    <p>{option.title}</p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </TooltipProvider>
  );
};
