/**
 * Settings API Service
 * Educational Note: Handles all API key management operations with the backend.
 * This service provides methods for CRUD operations on API keys stored in .env.
 */

import axios from 'axios';
import { API_BASE_URL } from './client';

export interface ApiKey {
  id: string;
  name: string;
  description: string;
  category: 'ai' | 'storage' | 'utility';
  required?: boolean;
  value: string;
  is_set: boolean;
}

export interface ApiKeyUpdate {
  id: string;
  value: string;
}

export interface ValidationResult {
  valid: boolean;
  message: string;
}

class SettingsAPI {
  /**
   * Get all API keys from the backend
   * Educational Note: Returns masked values for security
   */
  async getApiKeys(): Promise<ApiKey[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/api-keys`);
      return response.data.api_keys;
    } catch (error) {
      console.error('Error fetching API keys:', error);
      throw error;
    }
  }

  /**
   * Update multiple API keys
   * Educational Note: This triggers a backend .env update and potential Flask reload
   */
  async updateApiKeys(apiKeys: ApiKeyUpdate[]): Promise<void> {
    try {
      await axios.post(`${API_BASE_URL}/settings/api-keys`, {
        api_keys: apiKeys
      });
    } catch (error) {
      console.error('Error updating API keys:', error);
      throw error;
    }
  }

  /**
   * Delete a specific API key
   * Educational Note: Removes the key from .env file
   */
  async deleteApiKey(keyId: string): Promise<void> {
    try {
      await axios.delete(`${API_BASE_URL}/settings/api-keys/${keyId}`);
    } catch (error) {
      console.error('Error deleting API key:', error);
      throw error;
    }
  }

  /**
   * Validate an API key
   * Educational Note: Tests if an API key works by making a test request
   */
  async validateApiKey(keyId: string, value: string): Promise<ValidationResult> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/api-keys/validate`, {
        key_id: keyId,
        value: value
      });
      return {
        valid: response.data.valid,
        message: response.data.message
      };
    } catch (error) {
      console.error('Error validating API key:', error);
      return {
        valid: false,
        message: 'Validation failed'
      };
    }
  }
}

export const settingsAPI = new SettingsAPI();

// ============================================================================
// Processing Settings Types and API
// ============================================================================

export interface TierConfig {
  name: string;
  description: string;
  max_workers: number;
  pages_per_minute: number;
}

export interface AvailableTier extends TierConfig {
  tier: number;
}

export interface ProcessingSettings {
  anthropic_tier: number;
  tier_config: TierConfig;
}

class ProcessingSettingsAPI {
  /**
   * Get current processing settings
   * Educational Note: Returns the current tier configuration for parallel processing
   */
  async getSettings(): Promise<{ settings: ProcessingSettings; available_tiers: AvailableTier[] }> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/processing`);
      return {
        settings: response.data.settings,
        available_tiers: response.data.available_tiers,
      };
    } catch (error) {
      console.error('Error fetching processing settings:', error);
      throw error;
    }
  }

  /**
   * Update processing settings
   * Educational Note: Saves the selected tier to .env file
   */
  async updateSettings(settings: { anthropic_tier: number }): Promise<ProcessingSettings> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/processing`, settings);
      return response.data.settings;
    } catch (error) {
      console.error('Error updating processing settings:', error);
      throw error;
    }
  }
}

export const processingSettingsAPI = new ProcessingSettingsAPI();

// ============================================================================
// Google Drive Types and API
// ============================================================================

export interface GoogleStatus {
  configured: boolean;
  connected: boolean;
  email: string | null;
}

export interface GoogleFile {
  id: string;
  name: string;
  mime_type: string;
  size: number | null;
  modified_time: string;
  is_folder: boolean;
  is_google_file: boolean;
  export_extension: string | null;
  google_type: string | null;
  icon_link: string | null;
  thumbnail_link: string | null;
}

export interface GoogleFilesResponse {
  success: boolean;
  files: GoogleFile[];
  next_page_token: string | null;
  folder_id: string | null;
  error?: string;
}

class GoogleDriveAPI {
  /**
   * Get Google Drive connection status
   * Educational Note: Checks if OAuth is configured and if user is connected
   */
  async getStatus(): Promise<GoogleStatus> {
    try {
      const response = await axios.get(`${API_BASE_URL}/google/status`);
      return {
        configured: response.data.configured,
        connected: response.data.connected,
        email: response.data.email,
      };
    } catch (error) {
      console.error('Error fetching Google status:', error);
      return {
        configured: false,
        connected: false,
        email: null,
      };
    }
  }

  /**
   * Start Google OAuth flow
   * Educational Note: Returns the auth URL to redirect user to
   */
  async getAuthUrl(): Promise<string | null> {
    try {
      const response = await axios.get(`${API_BASE_URL}/google/auth`);
      return response.data.auth_url;
    } catch (error) {
      console.error('Error getting Google auth URL:', error);
      return null;
    }
  }

  /**
   * Disconnect Google Drive
   * Educational Note: Removes stored tokens
   */
  async disconnect(): Promise<boolean> {
    try {
      const response = await axios.post(`${API_BASE_URL}/google/disconnect`);
      return response.data.success;
    } catch (error) {
      console.error('Error disconnecting Google:', error);
      return false;
    }
  }

  /**
   * List files from Google Drive
   * Educational Note: Supports folder navigation and pagination
   */
  async listFiles(
    folderId?: string,
    pageSize: number = 50,
    pageToken?: string
  ): Promise<GoogleFilesResponse> {
    try {
      const params = new URLSearchParams();
      if (folderId) params.append('folder_id', folderId);
      if (pageSize) params.append('page_size', pageSize.toString());
      if (pageToken) params.append('page_token', pageToken);

      const response = await axios.get(`${API_BASE_URL}/google/files?${params}`);
      return response.data;
    } catch (error) {
      console.error('Error listing Google files:', error);
      return {
        success: false,
        files: [],
        next_page_token: null,
        folder_id: null,
        error: 'Failed to list files',
      };
    }
  }

  /**
   * Import a file from Google Drive to project sources
   * Educational Note: Downloads/exports file and creates source entry
   */
  async importFile(
    projectId: string,
    fileId: string,
    name?: string
  ): Promise<{ success: boolean; source?: unknown; error?: string }> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/sources/google-import`,
        { file_id: fileId, name }
      );
      return {
        success: true,
        source: response.data.source,
      };
    } catch (error) {
      console.error('Error importing from Google Drive:', error);
      return {
        success: false,
        error: 'Failed to import file',
      };
    }
  }
}

export const googleDriveAPI = new GoogleDriveAPI();