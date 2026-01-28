/**
 * BlogViewerModal Component
 * Educational Note: Modal for viewing blog post markdown content with images.
 * Renders markdown with proper styling for headings, lists, images.
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
import { Article, DownloadSimple, SpinnerGap, Image as ImageIcon } from '@phosphor-icons/react';
import { blogsAPI, type BlogJob } from '@/lib/api/studio';
import { API_HOST } from '@/lib/api/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface BlogViewerModalProps {
  projectId: string;
  viewingBlogJob: BlogJob | null;
  onClose: () => void;
  onDownload: (jobId: string) => void;
}

export const BlogViewerModal: React.FC<BlogViewerModalProps> = ({
  projectId,
  viewingBlogJob,
  onClose,
  onDownload,
}) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  // Fetch markdown content when modal opens
  useEffect(() => {
    if (viewingBlogJob) {
      setIsLoading(true);
      blogsAPI.getPreview(projectId, viewingBlogJob.id)
        .then((content) => {
          setMarkdownContent(content);
        })
        .catch(() => {
          setMarkdownContent('*Error loading blog post content*');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setMarkdownContent('');
    }
  }, [viewingBlogJob, projectId]);

  // Format word count for display
  const wordCountDisplay = viewingBlogJob?.word_count
    ? viewingBlogJob.word_count >= 1000
      ? `${(viewingBlogJob.word_count / 1000).toFixed(1)}k words`
      : `${viewingBlogJob.word_count} words`
    : '';

  const imageCount = viewingBlogJob?.images?.length || 0;

  return (
    <Dialog open={viewingBlogJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Article size={20} className="text-indigo-600" />
              <DialogTitle>
                {viewingBlogJob?.title || 'Blog Post'}
              </DialogTitle>
            </div>
            {viewingBlogJob && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDownload(viewingBlogJob.id)}
                className="flex items-center gap-1 mr-4"
              >
                <DownloadSimple size={14} />
                Download
              </Button>
            )}
          </div>
          <DialogDescription className="flex items-center gap-3">
            {wordCountDisplay && <span>{wordCountDisplay}</span>}
            {imageCount > 0 && (
              <span className="flex items-center gap-1">
                <ImageIcon size={12} />
                {imageCount} image{imageCount > 1 ? 's' : ''}
              </span>
            )}
            {viewingBlogJob?.target_keyword && (
              <span className="text-indigo-600">
                Keyword: {viewingBlogJob.target_keyword}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* Markdown Content */}
        <ScrollArea className="flex-1">
          <div className="px-6 py-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <SpinnerGap size={24} className="animate-spin text-indigo-500" />
                <span className="ml-2 text-muted-foreground">Loading blog post content...</span>
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
                    // Style images with proper API URL
                    img: ({ src, alt }) => {
                      // Handle IMAGE_N placeholders or direct URLs
                      const imageSrc = src?.startsWith('/api/')
                        ? `${API_HOST}${src}`
                        : src;
                      return (
                        <figure className="my-4">
                          <img
                            src={imageSrc}
                            alt={alt || 'Blog image'}
                            className="rounded-lg max-w-full h-auto shadow-md"
                          />
                          {alt && (
                            <figcaption className="text-center text-sm text-muted-foreground mt-2 italic">
                              {alt}
                            </figcaption>
                          )}
                        </figure>
                      );
                    },
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
                      <blockquote className="border-l-4 border-indigo-500 pl-4 my-4 italic text-muted-foreground">
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
                    // Style links
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        className="text-indigo-600 hover:text-indigo-700 underline"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {children}
                      </a>
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
