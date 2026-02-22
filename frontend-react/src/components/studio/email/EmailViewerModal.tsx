/**
 * EmailViewerModal Component
 * Educational Note: Modal for viewing and downloading email templates.
 * Displays preview iframe, color scheme, and download options.
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../ui/tooltip';
import { Button } from '../../ui/button';
import { ShareNetwork, DownloadSimple } from '@phosphor-icons/react';
import { emailsAPI, type EmailJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

interface EmailViewerModalProps {
  projectId: string;
  viewingEmailJob: EmailJob | null;
  onClose: () => void;
}

export const EmailViewerModal: React.FC<EmailViewerModalProps> = ({
  projectId,
  viewingEmailJob,
  onClose,
}) => {
  return (
    <Dialog open={viewingEmailJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShareNetwork size={20} className="text-blue-600" />
            {viewingEmailJob?.template_name || 'Email Template'}
          </DialogTitle>
          {viewingEmailJob?.subject_line && (
            <DialogDescription>
              Subject: {viewingEmailJob.subject_line}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Email Template Preview */}
        {viewingEmailJob?.preview_url && (
          <div className="py-4">
            {/* Preview iframe */}
            <div className="relative rounded-lg overflow-hidden border bg-gray-50 dark:bg-gray-900 mb-4">
              <iframe
                src={getAuthUrl(viewingEmailJob.preview_url)}
                className="w-full h-[600px]"
                title="Email template preview"
                sandbox="allow-same-origin"
              />
            </div>

            {/* Template Info */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Template Type</p>
                <p className="text-sm capitalize">{viewingEmailJob.template_type || 'N/A'}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Images</p>
                <p className="text-sm">{viewingEmailJob.images?.length || 0} image{viewingEmailJob.images?.length !== 1 ? 's' : ''}</p>
              </div>
            </div>

            {/* Color Scheme */}
            {viewingEmailJob.color_scheme && (
              <div className="mb-4">
                <p className="text-xs font-medium text-muted-foreground mb-2">Color Scheme</p>
                <div className="flex gap-2">
                  {Object.entries(viewingEmailJob.color_scheme).map(([name, color]) => (
                    <TooltipProvider key={name}>
                      <Tooltip>
                        <TooltipTrigger>
                          <div
                            className="w-8 h-8 rounded border border-gray-300 dark:border-gray-700"
                            style={{ backgroundColor: color }}
                          />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs capitalize">{name}: {color}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </div>
              </div>
            )}

            {/* Download Buttons */}
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="default"
                className="gap-1 flex-1"
                onClick={() => {
                  const downloadUrl = emailsAPI.getDownloadUrl(projectId, viewingEmailJob.id);
                  const link = document.createElement('a');
                  link.href = getAuthUrl(downloadUrl);
                  link.click();
                }}
              >
                <DownloadSimple size={14} />
                Download All (ZIP)
              </Button>
              <Button
                size="sm"
                variant="soft"
                className="gap-1"
                onClick={() => {
                  if (viewingEmailJob.html_url) {
                    const link = document.createElement('a');
                    link.href = getAuthUrl(viewingEmailJob.html_url);
                    link.download = viewingEmailJob.html_file || 'email_template.html';
                    link.click();
                  }
                }}
              >
                Download HTML
              </Button>
            </div>

            {/* Source info */}
            <p className="text-xs text-muted-foreground mt-4">
              Generated from: {viewingEmailJob.source_name}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
