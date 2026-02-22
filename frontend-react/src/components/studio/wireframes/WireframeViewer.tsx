/**
 * WireframeViewer Component
 * Educational Note: Renders wireframes using the Excalidraw React component.
 * We use convertToExcalidrawElements to convert skeleton elements to full
 * Excalidraw elements - this is the official way to create elements programmatically.
 */

import React, { useEffect, useState, useMemo } from 'react';
import { Excalidraw, convertToExcalidrawElements } from '@excalidraw/excalidraw';
import type { ExcalidrawImperativeAPI } from '@excalidraw/excalidraw/types';
import '@excalidraw/excalidraw/index.css';
import type { ExcalidrawElement } from '@/lib/api/studio/wireframes';

/**
 * Skeleton element for convertToExcalidrawElements
 * These are minimal element definitions that Excalidraw expands into full elements
 */
interface ElementSkeleton {
  type: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  text?: string;
  fontSize?: number;
  strokeColor?: string;
  backgroundColor?: string;
  points?: number[][];
}

interface WireframeViewerProps {
  elements: ExcalidrawElement[];
  title?: string;
}

export const WireframeViewer: React.FC<WireframeViewerProps> = ({
  elements,
}) => {
  const [excalidrawAPI, setExcalidrawAPI] = useState<ExcalidrawImperativeAPI | null>(null);

  // Convert our skeleton elements to full Excalidraw elements once
  const excalidrawElements = useMemo(() => {
    // Create minimal skeleton elements - only what's needed
    // Using 'as' assertion since convertToExcalidrawElements accepts flexible input
    const skeletons = elements.map((elem) => {
      const base: ElementSkeleton = {
        type: elem.type,
        x: elem.x ?? 0,
        y: elem.y ?? 0,
      };

      // Add styling if present
      if (elem.strokeColor) base.strokeColor = elem.strokeColor;
      if (elem.backgroundColor) base.backgroundColor = elem.backgroundColor;

      // Type-specific properties
      if (elem.type === 'text') {
        base.text = elem.text || 'Text';
        if (elem.fontSize) base.fontSize = elem.fontSize;
      } else if (elem.type === 'line' || elem.type === 'arrow') {
        base.points = elem.points || [[0, 0], [100, 0]];
      } else {
        base.width = elem.width ?? 100;
        base.height = elem.height ?? 50;
      }

      return base;
    });

    // Use Excalidraw's official conversion utility
    // Cast to expected type - convertToExcalidrawElements accepts flexible skeleton input
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const converted = convertToExcalidrawElements(skeletons as any);
    return converted;
  }, [elements]);

  // Scroll to content when ready
  useEffect(() => {
    if (excalidrawAPI && excalidrawElements.length > 0) {
      const timer = setTimeout(() => {
        excalidrawAPI.scrollToContent(excalidrawElements, { fitToViewport: true });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [excalidrawAPI, excalidrawElements]);

  return (
    <div style={{ height: '100%', width: '100%' }}>
      <Excalidraw
        excalidrawAPI={(api) => setExcalidrawAPI(api)}
        initialData={{
          elements: excalidrawElements,
          appState: {
            viewBackgroundColor: '#ffffff',
          },
          scrollToContent: true,
        }}
      />
    </div>
  );
};
