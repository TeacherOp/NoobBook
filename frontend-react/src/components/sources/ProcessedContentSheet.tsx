/**
 * ProcessedContentSheet Component
 * Educational Note: Sheet modal for viewing processed/extracted text from sources.
 * Displays the full extracted content with page markers in a scrollable view.
 * Only shows for text-based sources (PDF, DOCX, PPTX, TXT, Link, YouTube, Research).
 */

import React from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet';
import { ScrollArea } from '../ui/scroll-area';

interface ProcessedContentSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceName: string;
  content: string;
}

/**
 * Formats content by styling page markers for better visual hierarchy
 */
const formatContent = (content: string) => {
  // Split by page markers like "=== PDF PAGE 1 of 5 ===" or "=== TEXT PAGE 1 of 1 ==="
  const pageMarkerRegex = /(===\s*\w+\s*PAGE\s*\d+\s*of\s*\d+\s*===)/gi;
  const parts = content.split(pageMarkerRegex);

  return parts.map((part, index) => {
    // Reset lastIndex before test to avoid global regex state issues
    pageMarkerRegex.lastIndex = 0;
    if (pageMarkerRegex.test(part)) {
      return (
        <div
          key={index}
          className="mb-2 py-1.5 px-3 bg-[#f5f5f4] rounded-md text-xs font-medium text-stone-500 text-center border border-stone-200"
        >
          {part}
        </div>
      );
    }
    // Trim leading newlines from content after page markers
    const trimmedPart = part.replace(/^\n+/, '');
    if (!trimmedPart) return null;
    return <span key={index}>{trimmedPart}</span>;
  });
};

export const ProcessedContentSheet: React.FC<ProcessedContentSheetProps> = ({
  open,
  onOpenChange,
  sourceName,
  content,
}) => {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[95vw] sm:w-[800px] lg:w-[900px] max-w-[1000px] flex flex-col pr-0">
        <SheetHeader className="pb-4 border-b pr-6">
          <SheetTitle className="text-lg font-semibold pr-8" title={sourceName}>
            {sourceName}
          </SheetTitle>
        </SheetHeader>

        <ScrollArea className="flex-1 mt-4">
          <div className="pr-6 pb-8">
            <div className="text-[15px] text-stone-700 leading-7 whitespace-pre-wrap break-words tracking-normal">
              {formatContent(content)}
            </div>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
};
