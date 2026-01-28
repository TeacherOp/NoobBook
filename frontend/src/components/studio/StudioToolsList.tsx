/**
 * StudioToolsList Component
 * Educational Note: Renders all studio tools organized by category.
 * Uses StudioContext for signals and generation handling.
 */

import React from 'react';
import { ScrollArea } from '../ui/scroll-area';
import { StudioToolItem } from './StudioToolItem';
import { useStudioContext } from './StudioContext';
import {
  generationOptions,
  categoryMeta,
  getSignalsForItem,
  type GenerationCategory,
} from './types';

export const StudioToolsList: React.FC = () => {
  const { signals, handleGenerate } = useStudioContext();
  /**
   * Render tools for a specific category in a 2-column grid
   */
  const renderCategoryTools = (category: GenerationCategory) => {
    const options = generationOptions.filter((opt) => opt.category === category);
    return (
      <div className="grid grid-cols-2 gap-1.5">
        {options.map((option) => {
          const itemSignals = getSignalsForItem(signals, option.id);
          return (
            <StudioToolItem
              key={option.id}
              option={option}
              signals={itemSignals}
              onClick={handleGenerate}
            />
          );
        })}
      </div>
    );
  };

  /**
   * Check if any item in a category has signals
   */
  const categoryHasActiveItems = (category: GenerationCategory): boolean => {
    const options = generationOptions.filter((opt) => opt.category === category);
    return options.some((opt) => getSignalsForItem(signals, opt.id).length > 0);
  };

  /**
   * Render a category section with header and tools
   */
  const renderCategorySection = (category: GenerationCategory) => {
    const meta = categoryMeta[category];
    const Icon = meta.icon;
    const hasActiveItems = categoryHasActiveItems(category);

    return (
      <div key={category}>
        <div className="flex items-center gap-1.5 mb-1.5">
          <Icon
            size={12}
            className={hasActiveItems ? 'text-primary' : 'text-muted-foreground'}
          />
          <h3
            className={`text-[10px] font-medium uppercase tracking-wider ${
              hasActiveItems ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            {meta.label}
          </h3>
        </div>
        {renderCategoryTools(category)}
      </div>
    );
  };

  return (
    <ScrollArea className="flex-1">
      <div className="p-3 space-y-3">
        {renderCategorySection('learning')}
        {renderCategorySection('business')}
        {renderCategorySection('content')}
      </div>
    </ScrollArea>
  );
};
