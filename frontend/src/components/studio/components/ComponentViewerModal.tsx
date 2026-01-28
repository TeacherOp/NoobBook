/**
 * ComponentViewerModal Component
 * Educational Note: Modal for viewing and downloading UI components.
 * Displays component variations with iframe preview, copy code, and download options.
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../ui/tabs';
import { SquaresFour, Copy, DownloadSimple, Check } from '@phosphor-icons/react';
import { type ComponentJob } from '@/lib/api/studio';
import { API_HOST } from '@/lib/api/client';
import { useToast } from '../../ui/toast';

interface ComponentViewerModalProps {
  projectId: string;
  viewingComponentJob: ComponentJob | null;
  onClose: () => void;
}

export const ComponentViewerModal: React.FC<ComponentViewerModalProps> = ({
  projectId: _projectId,
  viewingComponentJob,
  onClose,
}) => {
  const { success: showSuccess } = useToast();
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyToClipboard = async (previewUrl: string, index: number) => {
    try {
      // Fetch the HTML content from the preview URL
      const response = await fetch(`${API_HOST}${previewUrl}`);
      const htmlContent = await response.text();

      await navigator.clipboard.writeText(htmlContent);
      setCopiedIndex(index);
      showSuccess('Code copied to clipboard!');

      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (error) {
      console.error('Failed to copy code:', error);
    }
  };

  const downloadComponent = (previewUrl: string, filename: string) => {
    const link = document.createElement('a');
    link.href = `${API_HOST}${previewUrl}`;
    link.download = filename;
    link.click();
  };

  return (
    <Dialog open={viewingComponentJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <SquaresFour size={20} className="text-purple-600" />
            {viewingComponentJob?.component_description || 'UI Components'}
          </DialogTitle>
          {viewingComponentJob?.component_category && (
            <DialogDescription>
              Category: <span className="capitalize">{viewingComponentJob.component_category}</span>
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Component Variations */}
        {viewingComponentJob?.components && viewingComponentJob.components.length > 0 && (
          <div className="py-4">
            <Tabs defaultValue="0" className="w-full">
              {/* Variation Tabs */}
              <TabsList className="w-full mb-4 h-auto flex-wrap">
                {viewingComponentJob.components.map((component, index) => (
                  <TabsTrigger key={index} value={index.toString()} className="flex-1">
                    {component.variation_name}
                  </TabsTrigger>
                ))}
              </TabsList>

              {/* Variation Content */}
              {viewingComponentJob.components.map((component, index) => (
                <TabsContent key={index} value={index.toString()} className="space-y-4">
                  {/* Description */}
                  <p className="text-sm text-muted-foreground">
                    {component.description}
                  </p>

                  {/* Preview iframe */}
                  <div className="relative rounded-lg overflow-hidden border bg-gray-50 dark:bg-gray-900">
                    <iframe
                      src={`${API_HOST}${component.preview_url}`}
                      className="w-full h-[500px]"
                      title={`${component.variation_name} preview`}
                      sandbox="allow-same-origin allow-scripts"
                    />
                  </div>

                  {/* Component Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Variation</p>
                      <p className="text-sm">{component.variation_name}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Code Size</p>
                      <p className="text-sm">{component.char_count.toLocaleString()} characters</p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="default"
                      className="gap-1 flex-1"
                      onClick={() => copyToClipboard(component.preview_url, index)}
                    >
                      {copiedIndex === index ? (
                        <>
                          <Check size={14} />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy size={14} />
                          Copy Code
                        </>
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      onClick={() => downloadComponent(component.preview_url, component.filename)}
                    >
                      <DownloadSimple size={14} />
                      Download HTML
                    </Button>
                  </div>
                </TabsContent>
              ))}
            </Tabs>

            {/* Usage Notes */}
            {viewingComponentJob.usage_notes && (
              <div className="mt-6 p-3 bg-muted/50 rounded-lg">
                <p className="text-xs font-medium text-muted-foreground mb-1">Usage Notes</p>
                <p className="text-sm whitespace-pre-wrap">{viewingComponentJob.usage_notes}</p>
              </div>
            )}

            {/* Source info */}
            <p className="text-xs text-muted-foreground mt-4">
              Generated from: {viewingComponentJob.source_name}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
