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

const log = createLogger('chats-api');

/**
 * Educational Note: A message in the conversation.
 * Each message has a role (user or assistant) and content.
 */
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
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

/**
 * Educational Note: Response from sending a message.
 * Contains both the user's message and the AI's response.
 */
export interface SendMessageResponse {
  user_message: Message;
  assistant_message: Message;
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
   * Send a message in a chat and get AI response
   * Educational Note: This sends the user's message to Claude API
   * and returns both the user message and AI response
   */
  async sendMessage(
    projectId: string,
    chatId: string,
    message: string
  ): Promise<SendMessageResponse> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/chats/${chatId}/messages`,
        { message }
      );
      return {
        user_message: response.data.user_message,
        assistant_message: response.data.assistant_message
      };
    } catch (error) {
      log.error({ err: error }, 'failed to send message');
      throw error;
    }
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
