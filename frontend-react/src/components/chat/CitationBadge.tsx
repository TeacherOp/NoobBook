/**
 * CitationBadge Component
 * Educational Note: Displays an inline citation number that shows
 * the actual chunk content on hover. Uses shadcn HoverCard and Card.
 * Citation format: [[cite:CHUNK_ID]] where chunk_id = {source_id}_page_{page}_chunk_{n}
 */

import React, { useState } from 'react';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '../ui/hover-card';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { FileText, CircleNotch } from '@phosphor-icons/react';
import { sourcesAPI, type ChunkContent } from '../../lib/api/sources';
import { createLogger } from '@/lib/logger';

const log = createLogger('citation-badge');

interface CitationBadgeProps {
  /** The citation number to display (e.g., 1, 2, 3) */
  citationNumber: number;
  /** The full chunk ID (format: {source_id}_page_{page}_chunk_{n}) */
  chunkId: string;
  /** The source UUID (extracted from chunk_id) */
  sourceId: string;
  /** The page number (extracted from chunk_id) */
  pageNumber: number;
  /** The project ID for API calls */
  projectId: string;
  /** Optional source name (if already known) */
  sourceName?: string;
}

/**
 * CitationBadge
 * Educational Note: This component renders an inline superscript citation
 * number using Badge. On hover, it fetches and displays the actual chunk
 * content from the source document using HoverCard and Card components.
 */
export const CitationBadge: React.FC<CitationBadgeProps> = ({
  citationNumber,
  chunkId,
  sourceId: _sourceId,
  pageNumber,
  projectId,
  sourceName,
}) => {
  const [chunkContent, setChunkContent] = useState<ChunkContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  /**
   * Fetch chunk content when hover card opens
   * Educational Note: We only fetch once and cache the result.
   */
  const handleOpenChange = async (open: boolean) => {
    if (open && !hasLoaded && !loading) {
      setLoading(true);
      setError(null);

      try {
        const content = await sourcesAPI.getCitationContent(
          projectId,
          chunkId
        );
        setChunkContent(content);
        setHasLoaded(true);
      } catch (err) {
        log.error({ err }, 'failed to Lfetching citation contentE');
        setError('Failed to load citation content');
      } finally {
        setLoading(false);
      }
    }
  };

  /**
   * Clean content for display
   * Educational Note: Source content may have extra whitespace, multiple
   * newlines, or formatting artifacts. This cleans it for readable display.
   */
  const cleanContent = (content: string): string => {
    return content
      // Replace multiple newlines with single newline
      .replace(/\n{3,}/g, '\n\n')
      // Replace multiple spaces with single space
      .replace(/[ \t]+/g, ' ')
      // Trim whitespace from each line
      .split('\n')
      .map(line => line.trim())
      .join('\n')
      // Final trim
      .trim();
  };

  return (
    <HoverCard openDelay={200} closeDelay={100} onOpenChange={handleOpenChange}>
      <HoverCardTrigger asChild>
        <Badge
          className="cursor-pointer text-[11px] px-2 py-0.5 h-[18px] align-super -mt-1 bg-primary text-primary-foreground hover:bg-primary/90 border-0"
        >
          {citationNumber}
        </Badge>
      </HoverCardTrigger>
      <HoverCardContent className="w-[28rem] p-0" side="top" align="start">
        <Card className="border-0 shadow-none">
          <CardHeader className="p-3 pb-2">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-primary flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <CardTitle className="text-sm font-medium truncate">
                  {chunkContent?.source_name || sourceName || 'Source'}
                </CardTitle>
                <CardDescription className="text-xs">
                  Page {pageNumber}
                  {chunkContent && chunkContent.chunk_index > 1 && `, Section ${chunkContent.chunk_index}`}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-3 pt-0 max-h-72 overflow-y-auto">
            {loading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-2">
                <CircleNotch size={14} className="animate-spin" />
                <span className="text-xs">Loading...</span>
              </div>
            ) : error ? (
              <p className="text-xs text-destructive">{error}</p>
            ) : chunkContent ? (
              <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {cleanContent(chunkContent.content)}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Loading content...
              </p>
            )}
          </CardContent>
        </Card>
      </HoverCardContent>
    </HoverCard>
  );
};
