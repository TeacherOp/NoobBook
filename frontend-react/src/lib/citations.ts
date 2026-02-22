/**
 * Citation Parser Utility
 * Educational Note: This utility parses citations from AI responses.
 * Claude uses the format [[cite:CHUNK_ID]] to cite sources.
 * Chunk ID format: {source_id}_page_{page}_chunk_{n}
 * We parse these, assign numbers, and prepare data for rendering.
 */

/**
 * Parsed citation data
 */
export interface Citation {
  /** The full citation marker (e.g., [[cite:abc123_page_5_chunk_1]]) */
  marker: string;
  /** The full chunk ID */
  chunkId: string;
  /** The source UUID (extracted from chunk ID) */
  sourceId: string;
  /** The page number (extracted from chunk ID) */
  pageNumber: number;
  /** The chunk index within the page */
  chunkIndex: number;
  /** Assigned citation number for display (e.g., [1], [2]) */
  citationNumber: number;
}

/**
 * Unique citation entry for the sources footer
 */
export interface CitationEntry {
  /** Assigned citation number */
  citationNumber: number;
  /** The full chunk ID */
  chunkId: string;
  /** The source UUID */
  sourceId: string;
  /** The page number */
  pageNumber: number;
  /** The chunk index */
  chunkIndex: number;
  /** Source name (filled in after fetching) */
  sourceName?: string;
}

/**
 * Result of parsing citations from text
 */
export interface ParsedContent {
  /** Array of all citations found (in order of appearance) */
  citations: Citation[];
  /** Unique citation entries for footer (deduplicated by chunk_id) */
  uniqueCitations: CitationEntry[];
  /** Map of marker -> citation number for quick lookup */
  markerToNumber: Map<string, number>;
}

// Regex to match citation format: [[cite:CHUNK_ID]]
// CHUNK_ID format: {source_id}_page_{page}_chunk_{n}
// source_id can contain alphanumeric chars and hyphens (UUID format)
const CITATION_REGEX = /\[\[cite:([a-zA-Z0-9_-]+_page_\d+_chunk_\d+)\]\]/g;

// Regex to parse chunk_id into components
const CHUNK_ID_REGEX = /^(.+)_page_(\d+)_chunk_(\d+)$/;

/**
 * Parse a chunk_id into its components
 */
function parseChunkId(chunkId: string): { sourceId: string; pageNumber: number; chunkIndex: number } | null {
  const match = chunkId.match(CHUNK_ID_REGEX);
  if (!match) return null;
  return {
    sourceId: match[1],
    pageNumber: parseInt(match[2], 10),
    chunkIndex: parseInt(match[3], 10),
  };
}

/**
 * Parse citations from AI response text
 *
 * Educational Note: This function extracts all citations from the text,
 * assigns sequential numbers to unique citations, and prepares data for
 * both inline rendering and the sources footer.
 *
 * @param text - The AI response text containing [[cite:...]] markers
 * @returns ParsedContent with citations, unique entries, and marker mapping
 */
export function parseCitations(text: string): ParsedContent {
  const citations: Citation[] = [];
  const uniqueCitations: CitationEntry[] = [];
  const markerToNumber = new Map<string, number>();

  // Track unique chunk_ids
  const seenChunkIds = new Map<string, number>();

  let match: RegExpExecArray | null;
  let citationCounter = 1;

  // Reset regex state
  CITATION_REGEX.lastIndex = 0;

  while ((match = CITATION_REGEX.exec(text)) !== null) {
    const marker = match[0];
    const chunkId = match[1];

    // Parse chunk_id to extract components
    const parsed = parseChunkId(chunkId);
    if (!parsed) continue;

    const { sourceId, pageNumber, chunkIndex } = parsed;

    let citationNumber: number;

    if (seenChunkIds.has(chunkId)) {
      // Reuse existing citation number for same chunk
      citationNumber = seenChunkIds.get(chunkId)!;
    } else {
      // Assign new citation number
      citationNumber = citationCounter++;
      seenChunkIds.set(chunkId, citationNumber);

      // Add to unique citations for footer
      uniqueCitations.push({
        citationNumber,
        chunkId,
        sourceId,
        pageNumber,
        chunkIndex,
      });
    }

    // Store marker -> number mapping
    markerToNumber.set(marker, citationNumber);

    // Add to citations array
    citations.push({
      marker,
      chunkId,
      sourceId,
      pageNumber,
      chunkIndex,
      citationNumber,
    });
  }

  return {
    citations,
    uniqueCitations,
    markerToNumber,
  };
}

/**
 * Check if text contains any citations
 *
 * @param text - The text to check
 * @returns true if text contains at least one citation
 */
export function hasCitations(text: string): boolean {
  CITATION_REGEX.lastIndex = 0;
  return CITATION_REGEX.test(text);
}

/**
 * Split text into segments (text and citation markers)
 *
 * Educational Note: This function splits the AI response into an array of
 * segments where each segment is either plain text or a citation marker.
 * This makes it easy to render the text with inline citation components.
 *
 * @param text - The AI response text
 * @returns Array of segments, each marked as 'text' or 'citation'
 */
export function splitTextWithCitations(
  text: string
): Array<{ type: 'text' | 'citation'; content: string; chunkId?: string; sourceId?: string; pageNumber?: number }> {
  const segments: Array<{
    type: 'text' | 'citation';
    content: string;
    chunkId?: string;
    sourceId?: string;
    pageNumber?: number;
  }> = [];

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // Reset regex state
  CITATION_REGEX.lastIndex = 0;

  while ((match = CITATION_REGEX.exec(text)) !== null) {
    // Add text before this citation
    if (match.index > lastIndex) {
      segments.push({
        type: 'text',
        content: text.slice(lastIndex, match.index),
      });
    }

    // Parse chunk_id
    const chunkId = match[1];
    const parsed = parseChunkId(chunkId);

    // Add the citation
    segments.push({
      type: 'citation',
      content: match[0],
      chunkId,
      sourceId: parsed?.sourceId,
      pageNumber: parsed?.pageNumber,
    });

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after last citation
  if (lastIndex < text.length) {
    segments.push({
      type: 'text',
      content: text.slice(lastIndex),
    });
  }

  return segments;
}

/**
 * Remove all citation markers from text
 *
 * @param text - The text with citation markers
 * @returns Clean text without citation markers
 */
export function stripCitations(text: string): string {
  return text.replace(CITATION_REGEX, '');
}
