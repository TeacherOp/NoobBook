/**
 * BusinessReportViewerModal Component
 * Educational Note: Modal for viewing business report markdown content with charts.
 * Renders markdown with proper styling for headings, charts, tables, and data visualizations.
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
import { ChartBar, DownloadSimple, SpinnerGap, ChartLine, PencilSimple } from '@phosphor-icons/react';
import { Input } from '../../ui/input';
import { businessReportsAPI, type BusinessReportJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ImageLightbox, type LightboxImage } from '../shared/ImageLightbox';

interface BusinessReportViewerModalProps {
  projectId: string;
  viewingBusinessReportJob: BusinessReportJob | null;
  onClose: () => void;
  onDownload: (jobId: string) => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const BusinessReportViewerModal: React.FC<BusinessReportViewerModalProps> = ({
  projectId,
  viewingBusinessReportJob,
  onClose,
  onDownload,
  onEdit,
  isGenerating,
  defaultEditInput = '',
}) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [editInput, setEditInput] = useState('');
  // Single-image lightbox state for embedded charts.
  const [lightboxImage, setLightboxImage] = useState<LightboxImage | null>(null);

  // Fetch markdown content when job changes
  useEffect(() => {
    if (viewingBusinessReportJob) {
      setIsLoading(true);
      businessReportsAPI.getPreview(projectId, viewingBusinessReportJob.id)
        .then((content) => {
          setMarkdownContent(content);
        })
        .catch(() => {
          setMarkdownContent('*Error loading business report content*');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setMarkdownContent('');
    }
  }, [viewingBusinessReportJob, projectId]);

  // Sync edit input separately to avoid re-fetching markdown
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  // Format word count for display
  const wordCountDisplay = viewingBusinessReportJob?.word_count
    ? viewingBusinessReportJob.word_count >= 1000
      ? `${(viewingBusinessReportJob.word_count / 1000).toFixed(1)}k words`
      : `${viewingBusinessReportJob.word_count} words`
    : '';

  const chartCount = viewingBusinessReportJob?.charts?.length || 0;
  const analysisCount = viewingBusinessReportJob?.analyses?.length || 0;

  // Get report type display name
  const getReportTypeDisplay = (type: string) => {
    const typeMap: Record<string, string> = {
      executive_summary: 'Executive Summary',
      financial_report: 'Financial Report',
      performance_analysis: 'Performance Analysis',
      market_research: 'Market Research',
      operations_report: 'Operations Report',
      sales_report: 'Sales Report',
      quarterly_review: 'Quarterly Review',
      annual_report: 'Annual Report',
    };
    return typeMap[type] || type.replace(/_/g, ' ');
  };

  return (
   <>
    <Dialog
      open={viewingBusinessReportJob !== null}
      onOpenChange={(open) => {
        if (!open) {
          // Same sibling-fragment teardown gap as BlogViewerModal:
          // ImageLightbox is mounted outside this Dialog, so the parent
          // closing doesn't clear lightboxImage on its own. Explicit
          // reset prevents the chart lightbox from outliving the report
          // it was opened from.
          setLightboxImage(null);
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between pr-6">
            <div className="flex items-center gap-2">
              <ChartBar size={20} className="text-teal-600" />
              <DialogTitle>
                {viewingBusinessReportJob?.title || 'Business Report'}
              </DialogTitle>
            </div>
            {viewingBusinessReportJob && (
              <Button
                variant="soft"
                size="sm"
                onClick={() => onDownload(viewingBusinessReportJob.id)}
                className="flex items-center gap-1"
              >
                <DownloadSimple size={14} />
                Download
              </Button>
            )}
          </div>
          <DialogDescription className="flex items-center gap-3 flex-wrap">
            {viewingBusinessReportJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-teal-600 bg-teal-500/10 px-1.5 py-0.5 rounded">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
            {viewingBusinessReportJob?.report_type && (
              <span className="text-teal-600 font-medium">
                {getReportTypeDisplay(viewingBusinessReportJob.report_type)}
              </span>
            )}
            {wordCountDisplay && <span>{wordCountDisplay}</span>}
            {chartCount > 0 && (
              <span className="flex items-center gap-1">
                <ChartLine size={12} />
                {chartCount} chart{chartCount > 1 ? 's' : ''}
              </span>
            )}
            {analysisCount > 0 && (
              <span className="text-muted-foreground">
                {analysisCount} data analysis
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* Markdown Content */}
        <ScrollArea className="flex-1">
          <div className="px-6 py-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <SpinnerGap size={24} className="animate-spin text-teal-500" />
                <span className="ml-2 text-muted-foreground">Loading business report content...</span>
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
                    // Style images (charts from ai_outputs/images/).
                    // Wrapped in a button so a click opens the shared
                    // lightbox with a Download button.
                    img: ({ src, alt }) => {
                      // Handle chart URLs - they may be relative API paths
                      // getAuthUrl handles both /api/ paths and full URLs
                      const imageSrc = src?.startsWith('/api/')
                        ? getAuthUrl(src)
                        : src;
                      if (!imageSrc) return null;
                      return (
                        <figure className="my-4">
                          <button
                            type="button"
                            onClick={() => setLightboxImage({
                              url: imageSrc,
                              alt: alt || 'Chart',
                              caption: alt || undefined,
                            })}
                            aria-label={`Open full-size view of ${alt || 'chart'}`}
                            className="block w-full cursor-zoom-in focus:outline-none focus:ring-2 focus:ring-amber-500 rounded-lg"
                          >
                            <img
                              src={imageSrc}
                              alt={alt || 'Chart'}
                              className="rounded-lg max-w-full h-auto shadow-md border border-border"
                            />
                          </button>
                          {alt && (
                            <figcaption className="text-center text-sm text-muted-foreground mt-2 italic">
                              {alt}
                            </figcaption>
                          )}
                        </figure>
                      );
                    },
                    // Style tables (common in business reports)
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
                    // Style blockquotes (for key findings, recommendations)
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-teal-500 pl-4 my-4 italic text-muted-foreground bg-teal-50/50 dark:bg-teal-950/30 py-2">
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
                        className="text-teal-600 hover:text-teal-700 underline"
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

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'add more charts', 'focus on Q4 results')"
                className="flex-1"
                disabled={isGenerating}
                onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && !isGenerating && onEdit(editInput.trim())}
              />
              <Button
                onClick={() => editInput.trim() && onEdit(editInput.trim())}
                disabled={!editInput.trim() || isGenerating}
                size="sm"
              >
                <PencilSimple size={14} className="mr-1" />
                Edit
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>

    <ImageLightbox
      open={lightboxImage !== null}
      image={lightboxImage}
      onClose={() => setLightboxImage(null)}
    />
   </>
  );
};
