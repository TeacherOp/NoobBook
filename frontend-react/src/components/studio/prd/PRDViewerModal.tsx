/**
 * PRDViewerModal Component
 * Educational Note: Modal for viewing PRD markdown content.
 * Renders markdown with proper styling for tables, lists, headings.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import { FileText, DownloadSimple, SpinnerGap } from '@phosphor-icons/react';
import { prdsAPI, type PRDJob } from '@/lib/api/studio';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface PRDViewerModalProps {
  projectId: string;
  viewingPRDJob: PRDJob | null;
  onClose: () => void;
  onDownload: (jobId: string) => void;
}

export const PRDViewerModal: React.FC<PRDViewerModalProps> = ({
  projectId,
  viewingPRDJob,
  onClose,
  onDownload,
}) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  // Fetch markdown content when modal opens
  useEffect(() => {
    if (viewingPRDJob) {
      setIsLoading(true);
      prdsAPI.getPreview(projectId, viewingPRDJob.id)
        .then((response) => {
          if (response.success && response.markdown_content) {
            setMarkdownContent(response.markdown_content);
          } else {
            setMarkdownContent('*Failed to load PRD content*');
          }
        })
        .catch(() => {
          setMarkdownContent('*Error loading PRD content*');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setMarkdownContent('');
    }
  }, [viewingPRDJob, projectId]);

  return (
    <Dialog open={viewingPRDJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText size={20} className="text-amber-600" />
              <DialogTitle>
                {viewingPRDJob?.document_title || 'Product Requirements Document'}
              </DialogTitle>
            </div>
            {viewingPRDJob && (
              <Button
                variant="soft"
                size="sm"
                onClick={() => onDownload(viewingPRDJob.id)}
                className="flex items-center gap-1"
              >
                <DownloadSimple size={14} />
                Download
              </Button>
            )}
          </div>
          {viewingPRDJob?.product_name && (
            <DialogDescription>
              {viewingPRDJob.product_name} - {viewingPRDJob.sections_written} sections
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Markdown Content */}
        <ScrollArea className="flex-1">
          <div className="px-6 py-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <SpinnerGap size={24} className="animate-spin text-amber-500" />
                <span className="ml-2 text-muted-foreground">Loading PRD content...</span>
              </div>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Style headings
                    h1: ({ children }) => (
                      <h1 className="text-2xl font-bold mt-6 mb-4 text-foreground">{children}</h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-xl font-semibold mt-5 mb-3 text-foreground border-b pb-2">{children}</h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="text-lg font-medium mt-4 mb-2 text-foreground">{children}</h3>
                    ),
                    // Style tables
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-4">
                        <table className="min-w-full border border-border rounded">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="px-3 py-2 bg-muted text-left text-sm font-medium border-b">{children}</th>
                    ),
                    td: ({ children }) => (
                      <td className="px-3 py-2 text-sm border-b border-border">{children}</td>
                    ),
                    // Style lists
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>
                    ),
                    // Style paragraphs
                    p: ({ children }) => (
                      <p className="my-2 text-foreground/90 leading-relaxed">{children}</p>
                    ),
                    // Style blockquotes
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-amber-500 pl-4 my-4 italic text-muted-foreground">
                        {children}
                      </blockquote>
                    ),
                    // Style code blocks
                    code: ({ className, children }) => {
                      const isInline = !className;
                      if (isInline) {
                        return (
                          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
                            {children}
                          </code>
                        );
                      }
                      return (
                        <code className="block bg-muted p-3 rounded text-sm font-mono overflow-x-auto">
                          {children}
                        </code>
                      );
                    },
                    // Style horizontal rules
                    hr: () => <hr className="my-6 border-border" />,
                    // Style strong/bold
                    strong: ({ children }) => (
                      <strong className="font-semibold text-foreground">{children}</strong>
                    ),
                  }}
                >
                  {markdownContent}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};
