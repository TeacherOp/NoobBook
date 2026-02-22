/**
 * StudioSignalPicker Component
 * Educational Note: Dialog for selecting which signal to generate from when multiple exist.
 * Allows user to choose between different topics/directions for the same studio item.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import type { StudioSignal, StudioItemId } from './types';

interface StudioSignalPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedItem: StudioItemId | null;
  selectedSignals: StudioSignal[];
  onSelectSignal: (itemId: StudioItemId, signal: StudioSignal) => void;
  getItemTitle: (itemId: StudioItemId) => string;
  getItemIcon: (itemId: StudioItemId) => React.ComponentType<{ size?: number; className?: string }> | undefined;
}

export const StudioSignalPicker: React.FC<StudioSignalPickerProps> = ({
  open,
  onOpenChange,
  selectedItem,
  selectedSignals,
  onSelectSignal,
  getItemTitle,
  getItemIcon,
}) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {selectedItem && getItemIcon(selectedItem) && (
              <span className="text-primary">
                {React.createElement(getItemIcon(selectedItem)!, { size: 20 })}
              </span>
            )}
            Generate {selectedItem ? getItemTitle(selectedItem) : ''}
          </DialogTitle>
          <DialogDescription>
            Multiple topics available. Choose which one to generate:
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2 py-4 max-h-[50vh] overflow-y-auto">
          {selectedSignals.map((signal) => (
            <Button
              key={signal.id}
              variant="soft"
              className="h-auto p-3 justify-start text-left flex flex-col items-start gap-1 w-full min-w-0"
              onClick={() => selectedItem && onSelectSignal(selectedItem, signal)}
            >
              <span className="font-medium text-sm line-clamp-2 w-full">
                {signal.direction}
              </span>
              <span className="text-xs text-muted-foreground">
                {signal.sources.length} source{signal.sources.length !== 1 ? 's' : ''}
              </span>
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};
