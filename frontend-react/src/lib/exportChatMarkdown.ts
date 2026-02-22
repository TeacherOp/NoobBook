/**
 * Export Chat as Markdown
 * Educational Note: Converts a chat conversation into a downloadable Markdown file.
 * Resolves [[cite:CHUNK_ID]] citations into numbered footnotes with source content.
 */

import { parseCitations } from './citations';
import { sourcesAPI, type ChunkContent } from './api/sources';
import type { Chat } from './api/chats';

/**
 * Convert a title into a filename-safe slug
 * Lowercase, hyphens for spaces, stripped special chars, max 50 chars
 */
function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 50);
}

/**
 * Format an ISO date string into a human-readable format
 * e.g. "January 15, 2026 at 3:45 PM"
 */
function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }) + ' at ' + date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Generate a markdown filename from the chat title
 * Format: {slug}-{YYYY-MM-DD}.md
 */
function generateMarkdownFilename(title: string): string {
  const slug = slugify(title) || 'chat-export';
  const date = new Date().toISOString().slice(0, 10);
  return `${slug}-${date}.md`;
}

interface ExportChatOptions {
  chat: Chat;
  projectId: string;
  projectName: string;
}

/**
 * Export a chat conversation as a Markdown file with resolved citations.
 *
 * Educational Note: This function:
 * 1. Scans all assistant messages for [[cite:CHUNK_ID]] markers
 * 2. Assigns global footnote numbers across the entire conversation
 * 3. Fetches citation content from the API in parallel
 * 4. Builds a formatted Markdown document with footnote references
 * 5. Triggers a browser download
 */
export async function exportChatAsMarkdown({
  chat,
  projectId,
  projectName,
}: ExportChatOptions): Promise<void> {
  const messages = chat.messages || [];

  // Step 1: Build a global citation map across all assistant messages
  // Each unique chunk_id gets one footnote number for the whole document
  const globalChunkToFootnote = new Map<string, number>();
  let footnoteCounter = 1;

  for (const msg of messages) {
    if (msg.role !== 'assistant') continue;
    const parsed = parseCitations(msg.content);
    for (const entry of parsed.uniqueCitations) {
      if (!globalChunkToFootnote.has(entry.chunkId)) {
        globalChunkToFootnote.set(entry.chunkId, footnoteCounter++);
      }
    }
  }

  // Step 2: Fetch all citation contents in parallel
  const citationContents = new Map<string, ChunkContent>();
  const fetchPromises = Array.from(globalChunkToFootnote.keys()).map(async (chunkId) => {
    try {
      const content = await sourcesAPI.getCitationContent(projectId, chunkId);
      citationContents.set(chunkId, content);
    } catch {
      // Gracefully skip citations that fail to fetch
    }
  });
  await Promise.all(fetchPromises);

  // Step 3: Build the markdown document
  const lines: string[] = [];

  // Header metadata
  lines.push(`# ${chat.title || 'Chat Export'}`);
  lines.push('');
  lines.push(`- **Project:** ${projectName}`);
  lines.push(`- **Created:** ${formatDate(chat.created_at)}`);
  lines.push(`- **Exported:** ${formatDate(new Date().toISOString())}`);
  lines.push(`- **Messages:** ${messages.length}`);
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('## Conversation');

  // Messages
  for (const msg of messages) {
    lines.push('');
    const roleName = msg.role === 'user' ? 'User' : 'NoobBook';
    lines.push(`### ${roleName}`);
    lines.push(`*${formatDate(msg.timestamp)}*`);
    lines.push('');

    let content = msg.content;

    // Replace citation markers with footnote references in assistant messages
    if (msg.role === 'assistant' && globalChunkToFootnote.size > 0) {
      content = content.replace(
        /\[\[cite:([a-zA-Z0-9_-]+_page_\d+_chunk_\d+)\]\]/g,
        (_match, chunkId: string) => {
          const footnoteNum = globalChunkToFootnote.get(chunkId);
          return footnoteNum ? `[^${footnoteNum}]` : '';
        }
      );
    }

    lines.push(content);
    lines.push('');
    lines.push('---');
  }

  // Citations section (only if there are citations)
  if (globalChunkToFootnote.size > 0) {
    lines.push('');
    lines.push('## Citations');
    lines.push('');

    for (const [chunkId, footnoteNum] of globalChunkToFootnote) {
      const citation = citationContents.get(chunkId);
      if (citation) {
        // Build location string: "Page X, Section Y" or just "Page X"
        const location = citation.chunk_index > 0
          ? `Page ${citation.page_number}, Section ${citation.chunk_index}`
          : `Page ${citation.page_number}`;
        lines.push(`[^${footnoteNum}]: **${citation.source_name}** - ${location}`);
        // Truncate content snippet to 200 chars
        const snippet = citation.content.length > 200
          ? citation.content.slice(0, 200) + '...'
          : citation.content;
        lines.push(`> ${snippet}`);
      } else {
        lines.push(`[^${footnoteNum}]: *Citation not available*`);
      }
      lines.push('');
    }
  }

  // Step 4: Trigger browser download
  const markdown = lines.join('\n');
  const blob = new Blob([markdown], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = generateMarkdownFilename(chat.title || 'Chat Export');
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
