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
import { ChartBar, DownloadSimple, SpinnerGap, ChartLine } from '@phosphor-icons/react';
import { businessReportsAPI, type BusinessReportJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface BusinessReportViewerModalProps {
  projectId: string;
  viewingBusinessReportJob: BusinessReportJob | null;
  onClose: () => void;
  onDownload: (jobId: string) => void;
}

export const BusinessReportViewerModal: React.FC<BusinessReportViewerModalProps> = ({
  projectId,
  viewingBusinessReportJob,
  onClose,
  onDownload,
}) => {
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  // Fetch markdown content when modal opens
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
    <Dialog open={viewingBusinessReportJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between">
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
                    // Style images (charts from ai_outputs/images/)
                    img: ({ src, alt }) => {
                      // Handle chart URLs - they may be relative API paths
                      // getAuthUrl handles both /api/ paths and full URLs
                      const imageSrc = src?.startsWith('/api/')
                        ? getAuthUrl(src)
                        : src;
                      return (
                        <figure className="my-4">
                          <img
                            src={imageSrc}
                            alt={alt || 'Chart'}
                            className="rounded-lg max-w-full h-auto shadow-md border border-border"
                          />
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
      </DialogContent>
    </Dialog>
  );
};
