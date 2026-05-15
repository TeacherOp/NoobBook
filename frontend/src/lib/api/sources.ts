/**
 * Sources API Service
 * Educational Note: Handles all source operations with the backend.
 * Sources are documents, images, audio, and data files uploaded to projects.
 */

import axios from 'axios';
import { API_BASE_URL } from './client';
import { createLogger } from '@/lib/logger';

const log = createLogger('sources-api');

/**
 * Source metadata returned from the API
 * Educational Note: Status transitions for sources:
 * - uploaded: File received, waiting for processing
 * - processing: Currently extracting text from PDF
 * - embedding: Creating vector embeddings for semantic search
 * - ready: Successfully processed, available for chat context
 * - error: Processing failed (no partial states - clean failure)
 */
export interface Source {
  id: string;
  project_id: string;
  name: string;
  description: string;
  /**
   * Backend source type (DOCUMENT/LINK/TEXT/CSV/DATABASE/etc).
   * Note: The backend stores the canonical file extension in `embedding_info.file_extension`.
   */
  type?: string;
  file_size: number;
  status: 'uploaded' | 'processing' | 'embedding' | 'ready' | 'error';
  active: boolean; // Whether source is included in chat context
  processing_info: Record<string, unknown> | null;
  embedding_info?: Record<string, unknown> | null; // Embedding details
  summary_info?: Record<string, unknown> | null;
  raw_file_path?: string | null;
  processed_file_path?: string | null;
  error_message?: string | null;
  url?: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Summary statistics for sources
 */
export interface SourcesSummary {
  total_count: number;
  total_size: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
}

/**
 * Allowed file extensions grouped by category
 */
export interface AllowedTypes {
  allowed_extensions: Record<string, string>;
  by_category: Record<string, string[]>;
}

// Maximum number of sources allowed per project
export const MAX_SOURCES = 100;

// Maximum image file size (1GB) - matches global upload limit
export const MAX_IMAGE_SIZE = 1024 * 1024 * 1024;

// Allowed file extensions by category
export const ALLOWED_EXTENSIONS = {
  document: ['.pdf', '.txt', '.docx', '.pptx', '.md', '.json', '.html', '.xml'],
  image: ['.jpeg', '.jpg', '.png', '.gif', '.webp'],
  audio: ['.mp3', '.wav', '.m4a', '.aac', '.flac'],
  data: ['.csv', '.xlsx'],
};

/**
 * Chunk content returned from citation API
 * Educational Note: This is used for the citation tooltip feature.
 * When Claude cites a source with [[cite:chunk_id]], we fetch the chunk content to display.
 * Chunk ID format: {source_id}_page_{page}_chunk_{n}
 */
export interface ChunkContent {
  content: string;
  chunk_id: string;
  source_id: string;
  source_name: string;
  page_number: number;
  chunk_index: number;
}

/**
 * Processed content returned from the processed content API
 * Educational Note: This is used for viewing extracted text from sources
 * in the Sources panel. Users can click on a processed source to see
 * the full extracted text with page markers.
 */
export interface ProcessedContent {
  content: string;
  source_name: string;
}

/**
 * Signed-URL payload for raw-file preview (PDF, IMAGE, AUDIO, CSV).
 * Backend returns a short-lived URL the browser can render natively —
 * <img>, <audio>, react-pdf, or a CSV table parser.
 */
export interface RawFileUrl {
  url: string;
  expires_in: number;
  source_name: string;
  type: string;
  mime_type?: string | null;
  file_extension?: string | null;
}

/**
 * File extensions that are viewable in the processed content viewer
 * Educational Note: Only text-based sources can be viewed.
 * Audio, image, and CSV files are excluded.
 */
export const VIEWABLE_EXTENSIONS = [
  '.pdf', '.txt', '.docx', '.pptx', '.md', '.json', '.html', '.xml',  // Documents
  '.link', '.research', '.mcp',                                          // Web content / MCP
];

export const NON_VIEWABLE_EXTENSIONS = [
  '.mp3', '.wav', '.m4a', '.aac', '.flac',  // Audio
  '.png', '.jpg', '.jpeg', '.gif', '.webp',  // Image
  '.csv',                                     // Data
];

/**
 * Get a source's file extension.
 * Educational Note: Prefer parsing from `source.name` (persists across renames),
 * but fall back to `embedding_info.file_extension` for sources with no extension
 * in the display name (e.g. DATABASE sources).
 */
export function getSourceFileExtension(source: Source): string {
  const name = source.name || '';
  const lastDot = name.lastIndexOf('.');
  const nameExtension = lastDot > 0 ? name.substring(lastDot).toLowerCase() : '';

  const embeddingExtension = ((source.embedding_info as Record<string, unknown>)?.file_extension as string | undefined);
  const embeddingExtLower = typeof embeddingExtension === 'string' ? embeddingExtension.toLowerCase() : '';

  return nameExtension || embeddingExtLower || '';
}

/**
 * Check if a source is viewable.
 *
 * The new type-aware SourcePreviewSheet renders every source type the
 * backend can hand us — PDFs through PDF.js, images via signed URL,
 * audio via <audio> + transcript, CSV as a table, and the
 * text-derivable types via markdown. As long as the source finished
 * processing, it's viewable.
 */
export function isSourceViewable(source: Source): boolean {
  return source.status === 'ready';
}

/**
 * Which preview view should render this source.
 *
 * Single source of truth for source-type → view routing. Both the
 * "fetch raw signed URL vs fetch processed text" decision and the
 * `renderBody` switch in SourcePreviewSheet derive from this — used
 * to be two parallel switches that drifted apart (the CSV-preview
 * regression came from one matching `type === 'CSV'` while the
 * upload pipeline writes `type === 'DATA'` for .csv files).
 *
 * Routing logic:
 *   - Match by file extension first (precise — `.csv`, `.pdf`).
 *   - Fall back to `source.type` for types that have no file (LINK,
 *     YOUTUBE, RESEARCH, DATABASE, MCP, FRESHDESK, JIRA, MIXPANEL).
 *   - `markdown` is the catch-all — covers TEXT, DOCX, PPTX, and
 *     every connection-style type whose preview body is the
 *     extracted-text file.
 */
export type SourceViewKind = 'pdf' | 'image' | 'audio' | 'csv' | 'markdown';

export function getViewKind(source: Source): SourceViewKind {
  const t = (source.type ?? '').toUpperCase();
  const ext = getSourceFileExtension(source);
  if (t === 'PDF' || ext === '.pdf') return 'pdf';
  if (t === 'IMAGE') return 'image';
  if (t === 'AUDIO') return 'audio';
  // CSV files upload as type='DATA' (category 'data' → upper) so the
  // .csv extension is the precise signal. DATABASE / MCP /
  // FRESHDESK / JIRA / MIXPANEL have no extension and correctly fall
  // through to markdown.
  if (ext === '.csv') return 'csv';
  return 'markdown';
}

class SourcesAPI {
  /**
   * List all sources for a project
   */
  async listSources(projectId: string): Promise<Source[]> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/sources`
      );
      return response.data.sources;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch sources');
      throw error;
    }
  }

  /**
   * Upload a new source file using chunked upload.
   *
   * Why chunked? The single-multipart upload path streams the whole
   * file body through the deployment's edge proxy (Cloudflare,
   * Traefik, etc.) and Flask, and most edge proxies cap body bytes at
   * 100 MB or less — so anything larger 413s before reaching us.
   * Slicing the file into ≤50 MB chunks before sending keeps every
   * single request under any reasonable proxy cap, so this works
   * out-of-the-box on any self-hosted deployment without DNS or proxy
   * config changes.
   *
   * Three round trips:
   *   1. POST upload-init  → mints a source_id and returns chunk_size.
   *   2. N × POST upload-chunk (multipart) — one per slice.
   *   3. POST upload-complete → assemble + create source row.
   *
   * The `uploadSource(...)` external signature is unchanged so existing
   * callers (e.g. SourcesPanel.handleFileUpload) keep working.
   */
  async uploadSource(
    projectId: string,
    file: File,
    name?: string,
    description?: string,
    onProgress?: (percent: number) => void
  ): Promise<Source> {
    try {
      // Step 1 — initialize the upload session.
      const initResp = await axios.post<{
        success: boolean;
        source_id: string;
        chunk_size: number;
        error?: string;
      }>(`${API_BASE_URL}/projects/${projectId}/sources/upload-init`, {
        filename: file.name,
        file_size: file.size,
      });
      if (!initResp.data.success) {
        throw new Error(initResp.data.error || 'Failed to initialize upload');
      }
      const { source_id, chunk_size } = initResp.data;
      // Defensive minimum — never use a tiny chunk size even if the
      // backend somehow returns one.
      const CHUNK = Math.max(chunk_size || 0, 1024 * 1024);

      // Step 2 — slice and send each chunk sequentially. We use sequential
      // (not parallel) to keep the temp-file write path simple on the
      // backend and to give the user a smooth, monotonic progress bar.
      //
      // Each chunk gets up to 3 attempts with exponential backoff. The
      // backend's chunk handler is idempotent at a given offset (writes
      // overwrite cleanly), so re-sending the same chunk is safe. This
      // turns a transient 502 / connection blip during a 1 GB upload
      // from "start over" into "lose ~1 chunk worth of bandwidth".
      const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK));
      const MAX_CHUNK_ATTEMPTS = 3;
      let bytesSent = 0;
      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK;
        const end = Math.min(start + CHUNK, file.size);
        const chunkBlob = file.slice(start, end);
        const chunkBytes = end - start;
        const beforeBytes = bytesSent;

        let lastErr: unknown;
        for (let attempt = 1; attempt <= MAX_CHUNK_ATTEMPTS; attempt++) {
          // FormData has to be re-created per attempt — the underlying
          // stream gets consumed by the first send.
          const formData = new FormData();
          formData.append('chunk', chunkBlob, file.name);
          formData.append('source_id', source_id);
          formData.append('offset', String(start));
          formData.append('total_size', String(file.size));

          try {
            await axios.post(
              `${API_BASE_URL}/projects/${projectId}/sources/upload-chunk`,
              formData,
              {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (evt) => {
                  if (!onProgress) return;
                  const chunkSentSoFar = evt.loaded || 0;
                  const overall = beforeBytes + Math.min(chunkSentSoFar, chunkBytes);
                  const pct = Math.round((overall / file.size) * 100);
                  onProgress(Math.min(pct, 99));
                },
              }
            );
            lastErr = undefined;
            break;
          } catch (err) {
            lastErr = err;
            // Don't retry on 4xx — those are deterministic failures
            // (permission denied, bad source_id, expired session).
            // Only network errors and 5xx are worth retrying.
            const status = (err as { response?: { status?: number } })?.response?.status;
            if (status && status >= 400 && status < 500) {
              break;
            }
            if (attempt < MAX_CHUNK_ATTEMPTS) {
              const backoff = 500 * 2 ** (attempt - 1); // 500ms, 1s, 2s
              await new Promise((r) => setTimeout(r, backoff));
            }
          }
        }
        if (lastErr) throw lastErr;

        bytesSent += chunkBytes;
      }

      // Step 3 — finalize: backend assembles + uploads to Supabase
      // Storage + creates the source row.
      const finalizeResp = await axios.post<{
        success: boolean;
        source: Source;
        error?: string;
      }>(`${API_BASE_URL}/projects/${projectId}/sources/upload-complete`, {
        source_id,
        filename: file.name,
        name,
        description,
        mime_type: file.type || undefined,
        total_size: file.size,
      });
      if (!finalizeResp.data.success) {
        throw new Error(finalizeResp.data.error || 'Failed to finalize upload');
      }

      // Now we can claim 100%.
      onProgress?.(100);
      return finalizeResp.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to upload source');
      throw error;
    }
  }

  /**
   * Get a specific source's metadata
   */
  async getSource(projectId: string, sourceId: string): Promise<Source> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}`
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch source');
      throw error;
    }
  }

  /**
   * Update a source's metadata
   */
  async updateSource(
    projectId: string,
    sourceId: string,
    data: { name?: string; description?: string; active?: boolean }
  ): Promise<Source> {
    try {
      const response = await axios.put(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}`,
        data
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to update source');
      throw error;
    }
  }

  /**
   * Delete a source
   */
  async deleteSource(projectId: string, sourceId: string): Promise<void> {
    try {
      await axios.delete(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}`
      );
    } catch (error) {
      log.error({ err: error }, 'failed to delete source');
      throw error;
    }
  }

  /**
   * Get the download URL for a source
   */
  getDownloadUrl(projectId: string, sourceId: string): string {
    return `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/download`;
  }

  /**
   * Get sources summary (counts and sizes)
   */
  async getSourcesSummary(projectId: string): Promise<SourcesSummary> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/sources/summary`
      );
      return response.data.summary;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch sources summary');
      throw error;
    }
  }

  /**
   * Get allowed file types for upload
   */
  async getAllowedTypes(): Promise<AllowedTypes> {
    try {
      const response = await axios.get(`${API_BASE_URL}/sources/allowed-types`);
      return {
        allowed_extensions: response.data.allowed_extensions,
        by_category: response.data.by_category,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to fetch allowed types');
      throw error;
    }
  }

  /**
   * Add a URL source (website or YouTube link)
   * Educational Note: URLs are stored as .link files containing JSON metadata.
   * The actual content fetching happens in a separate processing step.
   */
  async addUrlSource(
    projectId: string,
    url: string,
    name?: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/url`,
        { url, name, description }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add URL source');
      throw error;
    }
  }

  /**
   * Add a pasted text source
   * Educational Note: Text is stored as a .txt file. This is the simplest
   * source type - the raw content IS the processed content.
   */
  async addTextSource(
    projectId: string,
    content: string,
    name: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/text`,
        { content, name, description }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add text source');
      throw error;
    }
  }

  /**
   * Add a deep research source
   * Educational Note: Triggers an AI agent to research a topic and
   * synthesize findings into a comprehensive source document.
   */
  async addResearchSource(
    projectId: string,
    topic: string,
    description: string,
    links?: string[]
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/research`,
        { topic, description, links: links || [] }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add research source');
      throw error;
    }
  }

  /**
   * Add an MCP source from an account-level MCP connection
   * Educational Note: Snapshots selected resources from an MCP server,
   * embeds them, and makes them searchable in chat via RAG.
   */
  async addMcpSource(
    projectId: string,
    connectionId: string,
    resourceUris: string[],
    name?: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/mcp`,
        { connection_id: connectionId, resource_uris: resourceUris, name, description }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add MCP source');
      throw error;
    }
  }

  /**
   * Add a DATABASE source (Postgres/MySQL) from an account-level connection
   */
  async addDatabaseSource(
    projectId: string,
    connectionId: string,
    name?: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/database`,
        { connection_id: connectionId, name, description }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add database source');
      throw error;
    }
  }

  async addFreshdeskSource(
    projectId: string,
    name?: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/freshdesk`,
        { name, description }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add Freshdesk source');
      throw error;
    }
  }

  /**
   * Add a Jira source for live issue queries in chat
   * Educational Note: Jira credentials are configured globally in API Keys settings.
   * The backend uses these to connect to the Jira Cloud API.
   */
  async addJiraSource(
    projectId: string,
    name?: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/jira`,
        {
          name: name || undefined,
          description: description || undefined,
        }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add Jira source');
      throw error;
    }
  }

  /**
   * Add a Mixpanel source for live analytics queries in chat
   * Educational Note: Mixpanel Service Account credentials are configured
   * globally in API Keys settings. The backend uses these to query the
   * Mixpanel Query API live — no data is synced locally.
   */
  async addMixpanelSource(
    projectId: string,
    name?: string,
    description?: string
  ): Promise<Source> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/mixpanel`,
        {
          name: name || undefined,
          description: description || undefined,
        }
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to add Mixpanel source');
      throw error;
    }
  }

  async syncFreshdesk(projectId: string, sourceId: string): Promise<void> {
    try {
      await axios.post(`${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/freshdesk-sync`);
    } catch (error) {
      log.error({ err: error }, 'failed to sync Freshdesk');
      throw error;
    }
  }

  async backfillFreshdesk(projectId: string, sourceId: string): Promise<void> {
    try {
      await axios.post(`${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/freshdesk-backfill`);
    } catch (error) {
      log.error({ err: error }, 'failed to backfill Freshdesk');
      throw error;
    }
  }

  /**
   * Cancel processing for a source
   * Educational Note: This stops any running tasks and sets status back to "uploaded"
   * so user can retry later. Raw file is preserved, only processed data is deleted.
   */
  async cancelProcessing(projectId: string, sourceId: string): Promise<void> {
    try {
      await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/cancel`
      );
    } catch (error) {
      log.error({ err: error }, 'failed to cancel source processing');
      throw error;
    }
  }

  /**
   * Retry processing for a failed or uploaded source
   * Educational Note: This restarts processing from the raw file.
   */
  async retryProcessing(projectId: string, sourceId: string): Promise<void> {
    try {
      await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/retry`
      );
    } catch (error) {
      log.error({ err: error }, 'failed to retry source processing');
      throw error;
    }
  }

  /**
   * Get a chunk's content for citation display
   * Educational Note: This enables the citation feature. When Claude cites
   * a source with [[cite:CHUNK_ID]], we fetch the chunk content to display
   * in a tooltip/popover on hover.
   */
  async getCitationContent(
    projectId: string,
    chunkId: string
  ): Promise<ChunkContent> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/citations/${chunkId}`
      );
      return response.data.chunk;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch citation content');
      throw error;
    }
  }

  /**
   * Get the processed content of a source for viewing
   * Educational Note: This enables users to view the extracted text from
   * their sources. When a user clicks on a processed source in the Sources
   * panel, we fetch and display the full extracted text with page markers.
   */
  async getProcessedContent(
    projectId: string,
    sourceId: string
  ): Promise<ProcessedContent> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/processed`
      );
      return {
        content: response.data.content,
        source_name: response.data.source_name,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to fetch processed content');
      throw error;
    }
  }

  /**
   * Replace a TEXT source's body content and re-trigger processing.
   * Backend rejects non-TEXT types (other types require re-upload).
   */
  async updateSourceContent(
    projectId: string,
    sourceId: string,
    content: string,
    name?: string,
  ): Promise<Source> {
    try {
      const response = await axios.put(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/content`,
        { content, name },
      );
      return response.data.source;
    } catch (error) {
      log.error({ err: error }, 'failed to update source content');
      throw error;
    }
  }

  /**
   * Get a short-lived signed URL for a source's raw file.
   * Used by the preview modal for PDF / IMAGE / AUDIO / CSV. Backend
   * rejects raw previews for text-based types — those go through
   * getProcessedContent instead.
   */
  async getRawUrl(projectId: string, sourceId: string): Promise<RawFileUrl> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/sources/${sourceId}/raw`
      );
      return {
        url: response.data.url,
        expires_in: response.data.expires_in,
        source_name: response.data.source_name,
        type: response.data.type,
        mime_type: response.data.mime_type ?? null,
        file_extension: response.data.file_extension ?? null,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to fetch raw signed url');
      throw error;
    }
  }

  /**
   * Get the URL for an AI-generated image
   * Educational Note: AI agents like the CSV analyzer can generate images
   * (charts, plots). These are rendered in chat using [[image:FILENAME]]
   * syntax which gets converted to <img> tags pointing to this URL.
   */
  getAIImageUrl(projectId: string, filename: string): string {
    return `${API_BASE_URL}/projects/${projectId}/ai-images/${filename}`;
  }
}

export const sourcesAPI = new SourcesAPI();

/**
 * Helper function to format file size
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Helper function to get icon name based on category
 */
export function getCategoryIcon(category: string): string {
  switch (category) {
    case 'document':
      return 'FileText';
    case 'audio':
      return 'Music';
    case 'image':
      return 'Image';
    case 'data':
      return 'Table';
    case 'link':
      return 'Link';
    default:
      return 'File';
  }
}
