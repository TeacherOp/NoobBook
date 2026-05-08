/**
 * Chats API Service
 * Educational Note: Handles all chat operations with the backend.
 * This service provides methods for creating chats, sending messages,
 * and managing conversations with Claude AI.
 */

import axios from 'axios';
import type { StudioSignal } from '../../components/studio/types';
import { API_BASE_URL } from './client';
import { createLogger } from '@/lib/logger';
import { getAccessToken } from '../auth/session';
import type { CostTracking } from './projects';
import type { UserUsage } from './settings';

const log = createLogger('chats-api');

/**
 * Image block on a user message — rendered inline above the text in the
 * chat bubble. The backend supplies `url` as a freshly-signed URL on
 * every read, so the field is short-lived; do not persist it.
 */
export interface MessageImageBlock {
  type: 'image';
  url: string;
  media_type?: string;
  filename?: string;
}

export interface MessageTextBlock {
  type: 'text';
  text: string;
}

export type MessageContentBlock = MessageImageBlock | MessageTextBlock;

/**
 * Render a Message['content'] as a plain string. For block-content
 * messages with image attachments, returns the concatenated text
 * portion (image blocks are dropped). Use this for any callsite that
 * needs string operations (.replace, exporters, search index, etc.) —
 * the rich block representation lives only in the chat-bubble renderer.
 */
export function messageContentAsText(content: string | MessageContentBlock[]): string {
  if (typeof content === 'string') return content;
  return content
    .filter((b): b is MessageTextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('\n');
}

/**
 * Educational Note: A message in the conversation.
 * Each message has a role (user or assistant) and content. Content is a
 * plain string for text-only messages (the common case) and a list of
 * typed blocks when the user attached an inline image — image blocks
 * always come before text in the rendered order.
 */
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string | MessageContentBlock[];
  timestamp: string;
  model?: string;
  tokens?: {
    input: number;
    output: number;
  };
  error?: boolean;
}

/**
 * Educational Note: Chat metadata for list views.
 * Used when displaying a list of chats without loading full message history.
 */
export interface ChatMetadata {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

/**
 * Educational Note: Full chat data including all messages.
 * Loaded when user opens a specific chat.
 * Studio signals are imported from studio/types for type consistency.
 */
export interface Chat {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  studio_signals: StudioSignal[];
  selected_source_ids: string[] | null;
  metadata: {
    source_references: unknown[];
    sub_agents: unknown[];
  };
}

export interface ChatSyncChatMetadata {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  selected_source_ids: string[] | null;
}

export interface ChatSyncPayload {
  chat: ChatSyncChatMetadata;
  studio_signals: StudioSignal[];
  chat_costs: CostTracking;
  user_usage: UserUsage | null;
}

/**
 * Educational Note: Raw message for debug/raw view.
 * Includes the original content blocks (tool_use, tool_result, etc.)
 * that are normally filtered out for the normal chat display.
 */
export interface RawMessage {
  id: string;
  role: 'user' | 'assistant';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any;
  message_type: 'user_input' | 'ai_response' | 'tool_use' | 'tool_result';
  created_at: string;
  model?: string;
}

/**
 * Educational Note: Response from sending a message.
 * Contains both the user's message and the AI's response.
 */
export interface SendMessageResponse {
  user_message: Message;
  assistant_message: Message;
  sync?: ChatSyncPayload | null;
}

export type ChatStreamEvent =
  | { type: 'user_message'; payload: Message }
  | { type: 'assistant_delta'; payload: { delta: string } }
  | { type: 'assistant_done'; payload: { assistant_message: Message; sync?: ChatSyncPayload | null } }
  | { type: 'error'; payload: { message: string; assistant_message?: Message | null; sync?: ChatSyncPayload | null } };

export interface StreamMessageCallbacks {
  onEvent?: (event: ChatStreamEvent) => void;
  onUserMessage?: (message: Message) => void;
  onAssistantDelta?: (delta: string) => void;
  onAssistantDone?: (payload: { assistant_message: Message; sync?: ChatSyncPayload | null }) => void;
  onErrorEvent?: (payload: { message: string; assistant_message?: Message | null; sync?: ChatSyncPayload | null }) => void;
}

export interface StreamMessageResult {
  hadUserMessage: boolean;
  hadAssistantDelta: boolean;
  terminalEvent: 'assistant_done' | 'error' | null;
  terminalSync?: ChatSyncPayload | null;
}

/**
 * Educational Note: Prompt configuration from data/prompts/*.json files.
 * Each prompt defines model settings and the actual prompt text.
 * Note: Some prompts use user_message, others use user_message_template.
 */
export interface PromptConfig {
  name: string;
  description: string;
  model: string;
  max_tokens: number;
  temperature: number;
  system_prompt: string;
  user_message?: string;
  user_message_template?: string;
  filename: string;
  version?: string;
  created_at?: string;
  updated_at?: string;
}

class ChatsAPI {
  private notifyStreamEvent(
    event: ChatStreamEvent,
    callbacks?: StreamMessageCallbacks
  ) {
    callbacks?.onEvent?.(event);
    switch (event.type) {
      case 'user_message':
        callbacks?.onUserMessage?.(event.payload);
        break;
      case 'assistant_delta':
        callbacks?.onAssistantDelta?.(event.payload.delta);
        break;
      case 'assistant_done':
        callbacks?.onAssistantDone?.(event.payload);
        break;
      case 'error':
        callbacks?.onErrorEvent?.(event.payload);
        break;
    }
  }

  private processSseChunk(
    rawEvent: string,
    callbacks: StreamMessageCallbacks | undefined,
    state: StreamMessageResult,
  ) {
    let eventName = 'message';
    const dataLines: string[] = [];

    for (const line of rawEvent.split(/\r?\n/)) {
      if (!line || line.startsWith(':')) {
        continue;
      }
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    const payloadText = dataLines.join('\n');
    const payload = payloadText ? JSON.parse(payloadText) : {};

    switch (eventName) {
      case 'user_message':
        state.hadUserMessage = true;
        this.notifyStreamEvent({ type: 'user_message', payload }, callbacks);
        break;
      case 'assistant_delta':
        state.hadAssistantDelta = true;
        this.notifyStreamEvent({ type: 'assistant_delta', payload }, callbacks);
        break;
      case 'assistant_done':
        state.terminalEvent = 'assistant_done';
        state.terminalSync = payload.sync ?? null;
        this.notifyStreamEvent({ type: 'assistant_done', payload }, callbacks);
        break;
      case 'error':
        state.terminalEvent = 'error';
        state.terminalSync = payload.sync ?? null;
        this.notifyStreamEvent({ type: 'error', payload }, callbacks);
        break;
      case 'ping':
        break;
      default:
        log.warn({ eventName }, 'unknown chat stream event');
    }
  }

  /**
   * List all chats for a specific project
   * Educational Note: Returns chat metadata sorted by most recent first
   */
  async listChats(projectId: string): Promise<ChatMetadata[]> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/chats`
      );
      return response.data.chats;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch chats');
      throw error;
    }
  }

  /**
   * Create a new chat in a project
   * Educational Note: Creates a new conversation with empty message history
   */
  async createChat(projectId: string, title: string = 'New Chat'): Promise<ChatMetadata> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/chats`,
        { title }
      );
      return response.data.chat;
    } catch (error) {
      log.error({ err: error }, 'failed to create chat');
      throw error;
    }
  }

  /**
   * Get full chat data including all messages
   * Educational Note: Loads the complete conversation history
   */
  async getChat(projectId: string, chatId: string): Promise<Chat> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}`
      );
      return response.data.chat;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch chat');
      throw error;
    }
  }

  /**
   * Get raw messages for debug/raw view.
   * Educational Note: Returns ALL messages including tool_use and tool_result
   * intermediates with their original content blocks.
   */
  async getRawMessages(projectId: string, chatId: string): Promise<RawMessage[]> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}?raw=true`
      );
      return response.data.chat.messages;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch raw messages');
      throw error;
    }
  }

  /**
   * Send a message in a chat and get AI response
   * Educational Note: This sends the user's message to Claude API
   * and returns both the user message and AI response
   */
  async sendMessage(
    projectId: string,
    chatId: string,
    message: string,
    signal?: AbortSignal
  ): Promise<SendMessageResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}/messages`,
        { message },
        signal ? { signal } : undefined
      );
      return {
        user_message: response.data.user_message,
        assistant_message: response.data.assistant_message,
        sync: response.data.sync,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to send message');
      throw error;
    }
  }

  async streamMessage(
    projectId: string,
    chatId: string,
    message: string,
    callbacks?: StreamMessageCallbacks,
    signal?: AbortSignal,
    attachments?: File[]
  ): Promise<StreamMessageResult> {
    const token = getAccessToken();
    // Two transport shapes:
    //  - JSON (legacy, no attachments) — small body, no boundary parsing.
    //  - multipart/form-data (with attachments) — backend route detects
    //    Content-Type and dispatches; image files are uploaded inside
    //    the same request as the message text. Don't set Content-Type
    //    manually for FormData — the browser writes the multipart
    //    boundary automatically and a manual header would corrupt it.
    const hasAttachments = !!(attachments && attachments.length);
    const headers: Record<string, string> = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    let body: BodyInit;
    if (hasAttachments) {
      const form = new FormData();
      form.append('message', message);
      attachments!.forEach((file, idx) => {
        form.append('attachments', file, file.name || `attachment-${idx}`);
      });
      body = form;
    } else {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify({ message });
    }
    const response = await fetch(
      `${API_BASE_URL}/projects/${projectId}/chats/${chatId}/messages/stream`,
      {
        method: 'POST',
        headers,
        body,
        signal,
      }
    );

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      throw new Error(errorText || `Streaming request failed with status ${response.status}`);
    }

    if (!response.body) {
      throw new Error('Streaming response body is missing');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const state: StreamMessageResult = {
      hadUserMessage: false,
      hadAssistantDelta: false,
      terminalEvent: null,
      terminalSync: null,
    };
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        let boundaryIndex = buffer.indexOf('\n\n');
        while (boundaryIndex >= 0) {
          const rawEvent = buffer.slice(0, boundaryIndex).trim();
          buffer = buffer.slice(boundaryIndex + 2);
          if (rawEvent) {
            this.processSseChunk(rawEvent, callbacks, state);
          }
          boundaryIndex = buffer.indexOf('\n\n');
        }

        if (done) {
          const tail = buffer.trim();
          if (tail) {
            this.processSseChunk(tail, callbacks, state);
          }
          break;
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to stream message');
      throw error;
    } finally {
      reader.releaseLock();
    }

    return state;
  }

  /**
   * Update a chat's title
   * Educational Note: Allows users to rename chats for better organization
   */
  async updateChat(
    projectId: string,
    chatId: string,
    title: string
  ): Promise<ChatMetadata> {
    try {
      const response = await axios.put(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}`,
        { title }
      );
      return response.data.chat;
    } catch (error) {
      log.error({ err: error }, 'failed to update chat');
      throw error;
    }
  }

  /**
   * Update which sources are selected for a specific chat.
   * Educational Note: Per-chat source selection — each chat maintains its own
   * set of selected sources independently.
   */
  async updateChatSources(
    projectId: string,
    chatId: string,
    selectedSourceIds: string[]
  ): Promise<void> {
    try {
      await axios.put(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}`,
        { selected_source_ids: selectedSourceIds }
      );
    } catch (error) {
      log.error({ err: error }, 'failed to update chat sources');
      throw error;
    }
  }

  /**
   * Delete a chat and all its messages
   * Educational Note: This is a hard delete for simplicity
   */
  async deleteChat(projectId: string, chatId: string): Promise<void> {
    try {
      await axios.delete(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}`
      );
    } catch (error) {
      log.error({ err: error }, 'failed to delete chat');
      throw error;
    }
  }

  /**
   * Get per-chat cost and token breakdown.
   * Educational Note: Mirrors projectsAPI.getCosts but scoped to a single chat.
   */
  async getCosts(projectId: string, chatId: string): Promise<CostTracking> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}/costs`
      );
      return response.data.costs;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch chat costs');
      throw error;
    }
  }

  /**
   * Get the system prompt for a project (custom or default)
   * Educational Note: Returns the prompt that will be used
   * for all AI conversations in this project
   */
  async getProjectPrompt(projectId: string): Promise<string> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/prompt`
      );
      return response.data.prompt;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch project prompt');
      throw error;
    }
  }

  /**
   * Get the global default prompt
   * Educational Note: This is the fallback prompt used when
   * projects don't have custom prompts
   */
  async getDefaultPrompt(): Promise<string> {
    try {
      const response = await axios.get(`${API_BASE_URL}/prompts/default`);
      return response.data.prompt;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch default prompt');
      throw error;
    }
  }

  /**
   * Get all prompt configurations
   * Educational Note: Returns all prompts from the data/prompts/ directory.
   * Each prompt includes model, temperature, max_tokens, system_prompt, and user_message.
   */
  async getAllPrompts(): Promise<PromptConfig[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/prompts/all`);
      return response.data.prompts;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch all prompts');
      throw error;
    }
  }

  /**
   * Update the project's custom system prompt
   * Educational Note: This allows users to customize how the AI behaves
   * for a specific project. Pass null to reset to default prompt.
   */
  async updateProjectPrompt(
    projectId: string,
    prompt: string | null
  ): Promise<{ prompt: string; is_custom: boolean }> {
    try {
      const response = await axios.put(
        `${API_BASE_URL}/projects/${projectId}/prompt`,
        { prompt }
      );
      return {
        prompt: response.data.prompt,
        is_custom: response.data.is_custom
      };
    } catch (error) {
      log.error({ err: error }, 'failed to update project prompt');
      throw error;
    }
  }

  /**
   * Get ElevenLabs configuration for real-time transcription
   * Educational Note: Returns WebSocket URL with embedded single-use token.
   * The token is generated server-side and expires after 15 minutes.
   * Always fetch a new config before starting a recording session.
   *
   * Security Note: The API key never leaves the server - only the token
   * is embedded in the WebSocket URL for authentication.
   */
  async getTranscriptionConfig(): Promise<{
    websocket_url: string;
    model_id: string;
    sample_rate: number;
    encoding: string;
  }> {
    try {
      const response = await axios.get(`${API_BASE_URL}/transcription/config`);
      if (response.data.success) {
        return {
          websocket_url: response.data.websocket_url,
          model_id: response.data.model_id,
          sample_rate: response.data.sample_rate,
          encoding: response.data.encoding,
        };
      } else {
        throw new Error(response.data.error || 'Failed to get transcription config');
      }
    } catch (error) {
      log.error({ err: error }, 'failed to fetch transcription config');
      throw error;
    }
  }

  /**
   * Check if transcription is configured
   * Educational Note: Lightweight check to see if ElevenLabs API key is set.
   */
  async isTranscriptionConfigured(): Promise<boolean> {
    try {
      const response = await axios.get(`${API_BASE_URL}/transcription/status`);
      return response.data.success && response.data.configured;
    } catch (error) {
      log.error({ err: error }, 'failed to check transcription status');
      return false;
    }
  }
}

export const chatsAPI = new ChatsAPI();

// Re-export StudioSignal for convenience (single source of truth from studio/types)
export type { StudioSignal } from '../../components/studio/types';
