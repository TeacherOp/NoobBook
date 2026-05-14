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
import { Input } from '../../ui/input';
import { SquaresFour, Copy, DownloadSimple, Check, PencilSimple } from '@phosphor-icons/react';
import { type ComponentJob } from '@/lib/api/studio';
import { api, getAuthUrl } from '@/lib/api/client';
import { useToast } from '../../ui/use-toast';
import { copyToClipboard } from '@/lib/clipboard';
import { createLogger } from '@/lib/logger';

const log = createLogger('component-viewer');

interface ComponentViewerModalProps {
  projectId: string;
  viewingComponentJob: ComponentJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
}

const ComponentEditBar: React.FC<{ onEdit: (instructions: string) => void }> = ({ onEdit }) => {
  const [editInput, setEditInput] = useState('');

  const handleEdit = () => {
    const trimmed = editInput.trim();
    if (!trimmed) return;
    onEdit(trimmed);
    setEditInput('');
  };

  return (
    <div className="flex gap-2 pt-4 border-t-2 border-orange-200 bg-orange-50/30 px-1 pb-1 rounded-b-lg">
      <Input
        value={editInput}
        onChange={(e) => setEditInput(e.target.value)}
        placeholder="Describe changes... (e.g., 'more padding', 'horizontal layout')"
        className="flex-1"
        onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && handleEdit()}
      />
      <Button onClick={handleEdit} disabled={!editInput.trim()} size="sm">
        <PencilSimple size={14} className="mr-1" />
        Edit
      </Button>
    </div>
  );
};

export const ComponentViewerModal: React.FC<ComponentViewerModalProps> = ({
  viewingComponentJob,
  onClose,
  onEdit,
}) => {
  const { success: showSuccess, error: showError } = useToast();
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopyHtml = async (previewUrl: string, index: number) => {
    try {
      const response = await api.get(previewUrl, { responseType: 'text' });
      const htmlContent = response.data;

      const ok = await copyToClipboard(htmlContent);
      if (ok) {
        setCopiedIndex(index);
        showSuccess('Code copied to clipboard!');
        setTimeout(() => setCopiedIndex(null), 2000);
      } else {
        showError('Could not copy. Select the code manually.');
      }
    } catch (err) {
      log.error({ err }, 'failed to fetch component HTML');
      showError('Failed to load component code');
    }
  };

  const downloadComponent = (previewUrl: string, filename: string) => {
    const link = document.createElement('a');
    link.href = getAuthUrl(previewUrl);
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

        {/* Empty-state body. A finished job can legitimately have zero
            components if the model's tool call was truncated mid-output
            (max_tokens hit) — the agent now marks those as error, but
            older runs that landed as ready=[] still exist in the DB.
            Showing a real explanation + an Edit bar (so the user can
            retry with the saved variations_planned context) is much
            better than rendering an empty dialog.
            Gated on terminal statuses only — `pending` and `processing`
            jobs legitimately have zero components mid-flight, and
            surfacing "Generation didn't finish" while it's still running
            would be a wrong-state render the user would (rightly) read
            as a bug. */}
        {viewingComponentJob
          && (!viewingComponentJob.components || viewingComponentJob.components.length === 0)
          && !['pending', 'processing'].includes(viewingComponentJob.status)
          && (
          <div className="py-6 flex flex-col gap-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-900 p-4 text-sm">
              <p className="font-medium text-amber-900 dark:text-amber-200">
                {viewingComponentJob.status === 'error'
                  ? 'Generation didn’t finish'
                  : 'No components to show yet'}
              </p>
              <p className="text-amber-800 dark:text-amber-300 mt-1">
                {viewingComponentJob.error_message
                  || 'The model finished without writing component code. This usually means the output ran past the token cap or the tool call was malformed. Use the prompt below to retry — the saved plan will be reused.'}
              </p>
              {viewingComponentJob.variations_planned?.length ? (
                <p className="text-xs text-amber-700 dark:text-amber-400 mt-2">
                  {viewingComponentJob.variations_planned.length} variation{viewingComponentJob.variations_planned.length === 1 ? '' : 's'} were planned: {viewingComponentJob.variations_planned.map((v) => v.variation_name).join(', ')}.
                </p>
              ) : null}
            </div>
            {onEdit && (
              <ComponentEditBar key={viewingComponentJob?.id || 'component-empty-edit'} onEdit={onEdit} />
            )}
            <p className="text-xs text-muted-foreground">
              Generated from: {viewingComponentJob.source_name || 'unknown source'}
            </p>
          </div>
        )}

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
                      src={getAuthUrl(component.preview_url)}
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
                      onClick={() => handleCopyHtml(component.preview_url, index)}
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
                      variant="soft"
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

            {onEdit && (
              <ComponentEditBar key={viewingComponentJob?.id || 'component-edit'} onEdit={onEdit} />
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
