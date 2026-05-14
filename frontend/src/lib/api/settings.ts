/**
 * Settings API Service
 * Educational Note: Handles all API key management operations with the backend.
 * This service provides methods for CRUD operations on API keys stored in .env.
 */

import axios from 'axios';
import { API_BASE_URL } from './client';
import { createLogger } from '@/lib/logger';

const log = createLogger('settings-api');

export interface ApiKey {
  id: string;
  name: string;
  description: string;
  category: 'ai' | 'storage' | 'utility' | 'integrations' | 'observability';
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
  warning?: boolean;
  message: string;
}

export type DatabaseType = 'postgresql' | 'mysql';

export interface DatabaseConnection {
  id: string;
  name: string;
  description: string;
  db_type: DatabaseType;
  connection_uri_masked: string;
  is_active: boolean;
  visible_to_all: boolean;
  created_at: string;
  updated_at: string;
}

export type ResetFrequency = 'daily' | 'weekly' | 'monthly' | null;

export interface UserSummary {
  id: string;
  email: string | null;
  role: 'admin' | 'user' | string;
  cost_limit: number | null;
  reset_frequency: ResetFrequency;
  period_spend: number;
  period_start: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserUsage {
  cost_limit: number | null;
  reset_frequency: ResetFrequency;
  current_spend: number;
  total_spend: number;
  period_start: string | null;
  usage_percent: number;
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
      log.error({ err: error }, 'failed to fetch API keys');
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
      log.error({ err: error }, 'failed to update API keys');
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
      log.error({ err: error }, 'failed to delete API key');
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
        warning: response.data.warning ?? false,
        message: response.data.message
      };
    } catch (error) {
      log.error({ err: error }, 'failed to validate API key');
      return {
        valid: false,
        message: 'Validation failed'
      };
    }
  }
}

export const settingsAPI = new SettingsAPI();

// ============================================================================
// Database Connections Types and API
// ============================================================================

class DatabasesAPI {
  async listDatabases(): Promise<DatabaseConnection[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/databases`);
      return response.data.databases || [];
    } catch (error) {
      log.error({ err: error }, 'failed to fetch databases');
      throw error;
    }
  }

  async createDatabase(payload: {
    name: string;
    db_type: DatabaseType;
    connection_uri: string;
    description?: string;
  }): Promise<DatabaseConnection> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/databases`, payload);
      return response.data.database;
    } catch (error) {
      log.error({ err: error }, 'failed to create database');
      throw error;
    }
  }

  async deleteDatabase(connectionId: string): Promise<void> {
    try {
      await axios.delete(`${API_BASE_URL}/settings/databases/${connectionId}`);
    } catch (error) {
      log.error({ err: error }, 'failed to delete database');
      throw error;
    }
  }

  async updateVisibility(connectionId: string, visibleToAll: boolean): Promise<DatabaseConnection> {
    try {
      const response = await axios.patch(
        `${API_BASE_URL}/settings/databases/${connectionId}/visibility`,
        { visible_to_all: visibleToAll }
      );
      return response.data.database;
    } catch (error) {
      log.error({ err: error }, 'failed to update database visibility');
      throw error;
    }
  }

  async validateDatabase(dbType: DatabaseType, connectionUri: string): Promise<ValidationResult> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/databases/validate`, {
        db_type: dbType,
        connection_uri: connectionUri,
      });
      return {
        valid: response.data.valid,
        message: response.data.message,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to validate database');
      const axiosErr = error as { response?: { data?: { error?: string; message?: string } } };
      return {
        valid: false,
        message: axiosErr.response?.data?.error || axiosErr.response?.data?.message || 'Validation failed',
      };
    }
  }
}

export const databasesAPI = new DatabasesAPI();

// ============================================================================
// MCP Connections Types and API
// ============================================================================

export type McpAuthType = 'none' | 'bearer' | 'api_key' | 'header';
export type McpTransport = 'sse' | 'stdio';

export interface McpStdioConfig {
  command: string;
  args: string[];
  env_masked?: Record<string, string>;
}

export interface McpToolSummary {
  name: string;
  description: string;
}

export interface McpConnection {
  id: string;
  name: string;
  description: string;
  server_url: string;
  transport: McpTransport;
  auth_type: McpAuthType;
  auth_config_masked: Record<string, string> | null;
  stdio_config: McpStdioConfig | null;
  tools_enabled: boolean;
  cached_tools: McpToolSummary[] | null;
  tools_cached_at: string | null;
  is_active: boolean;
  visible_to_all: boolean;
  created_at: string;
  updated_at: string;
}

export interface McpResource {
  uri: string;
  name: string;
  description: string;
  mime_type: string | null;
}

export interface McpTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

class McpAPI {
  async listConnections(): Promise<McpConnection[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/mcp`);
      return response.data.connections || [];
    } catch (error) {
      log.error({ err: error }, 'failed to fetch MCP connections');
      throw error;
    }
  }

  async createConnection(payload: {
    name: string;
    transport?: McpTransport;
    server_url?: string;
    auth_type?: McpAuthType;
    auth_config?: Record<string, string>;
    stdio_config?: { command: string; args: string[]; env?: Record<string, string> };
    description?: string;
    tools_enabled?: boolean;
  }): Promise<McpConnection> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/mcp`, payload);
      return response.data.connection;
    } catch (error) {
      log.error({ err: error }, 'failed to create MCP connection');
      throw error;
    }
  }

  async deleteConnection(connectionId: string): Promise<void> {
    try {
      await axios.delete(`${API_BASE_URL}/settings/mcp/${connectionId}`);
    } catch (error) {
      log.error({ err: error }, 'failed to delete MCP connection');
      throw error;
    }
  }

  async updateVisibility(connectionId: string, visibleToAll: boolean): Promise<McpConnection> {
    try {
      const response = await axios.patch(
        `${API_BASE_URL}/settings/mcp/${connectionId}/visibility`,
        { visible_to_all: visibleToAll }
      );
      return response.data.connection;
    } catch (error) {
      log.error({ err: error }, 'failed to update MCP visibility');
      throw error;
    }
  }

  async updateToolsEnabled(connectionId: string, enabled: boolean): Promise<McpConnection> {
    try {
      const response = await axios.patch(
        `${API_BASE_URL}/settings/mcp/${connectionId}/tools-enabled`,
        { tools_enabled: enabled }
      );
      return response.data.connection;
    } catch (error) {
      log.error({ err: error }, 'failed to update MCP tools-enabled');
      throw error;
    }
  }

  async validateConnection(payload: {
    transport?: McpTransport;
    server_url?: string;
    auth_type?: McpAuthType;
    auth_config?: Record<string, string>;
    stdio_config?: { command: string; args: string[]; env?: Record<string, string> };
  }): Promise<ValidationResult> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/mcp/validate`, {
        transport: payload.transport || 'sse',
        server_url: payload.server_url || '',
        auth_type: payload.auth_type || 'none',
        auth_config: payload.auth_config || {},
        stdio_config: payload.stdio_config || {},
      });
      return {
        valid: response.data.valid,
        message: response.data.message,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to validate MCP connection');
      const axiosErr = error as { response?: { data?: { error?: string; message?: string } } };
      return {
        valid: false,
        message: axiosErr.response?.data?.error || axiosErr.response?.data?.message || 'Validation failed',
      };
    }
  }

  async listResources(connectionId: string): Promise<McpResource[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/mcp/${connectionId}/resources`);
      return response.data.resources || [];
    } catch (error) {
      log.error({ err: error }, 'failed to list MCP resources');
      throw error;
    }
  }

  async listTools(connectionId: string): Promise<McpTool[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/mcp/${connectionId}/tools`);
      return response.data.tools || [];
    } catch (error) {
      log.error({ err: error }, 'failed to list MCP tools');
      throw error;
    }
  }

  async refreshTools(connectionId: string): Promise<McpTool[]> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/mcp/${connectionId}/refresh-tools`);
      return response.data.tools || [];
    } catch (error) {
      log.error({ err: error }, 'failed to refresh MCP tools');
      throw error;
    }
  }
}

export const mcpAPI = new McpAPI();

// ============================================================================
// Users (RBAC) Types and API
// ============================================================================

class UsersAPI {
  async listUsers(): Promise<UserSummary[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/users`);
      return response.data.users || [];
    } catch (error) {
      log.error({ err: error }, 'failed to fetch users');
      throw error;
    }
  }

  async createUser(email: string, role: 'admin' | 'user' = 'user'): Promise<{ user: UserSummary; password: string }> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/users`, { email, role });
      return {
        user: response.data.user,
        password: response.data.password,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to create user');
      throw error;
    }
  }

  async deleteUser(userId: string): Promise<void> {
    try {
      await axios.delete(`${API_BASE_URL}/settings/users/${userId}`);
    } catch (error) {
      log.error({ err: error }, 'failed to delete user');
      throw error;
    }
  }

  async updateUserRole(userId: string, role: 'admin' | 'user'): Promise<UserSummary> {
    try {
      const response = await axios.put(`${API_BASE_URL}/settings/users/${userId}/role`, { role });
      return response.data.user;
    } catch (error) {
      log.error({ err: error }, 'failed to update user role');
      throw error;
    }
  }

  async resetPassword(userId: string): Promise<{ password: string }> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/users/${userId}/reset-password`);
      return { password: response.data.password };
    } catch (error) {
      log.error({ err: error }, 'failed to reset password');
      throw error;
    }
  }

  /**
   * Get permissions for a specific user
   * Educational Note: Returns the category-based permission structure that
   * controls which features are available to this user.
   */
  async getUserPermissions(userId: string): Promise<{
    permissions: UserPermissions;
    connections: { databases: { id: string; name: string }[]; mcp: { id: string; name: string }[] };
    connection_access: { database_ids: string[]; mcp_ids: string[] };
  }> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/users/${userId}/permissions`);
      return {
        permissions: response.data.permissions,
        connections: response.data.connections || { databases: [], mcp: [] },
        connection_access: response.data.connection_access || { database_ids: [], mcp_ids: [] },
      };
    } catch (error) {
      log.error({ err: error }, 'failed to fetch user permissions');
      throw error;
    }
  }

  /**
   * Update permissions for a specific user (including per-connection access)
   */
  async updateUserPermissions(
    userId: string,
    permissions: UserPermissions,
    connectionAccess?: { database_ids?: string[]; mcp_ids?: string[] },
  ): Promise<void> {
    try {
      await axios.put(`${API_BASE_URL}/settings/users/${userId}/permissions`, {
        permissions,
        connection_access: connectionAccess,
      });
    } catch (error) {
      log.error({ err: error }, 'failed to update user permissions');
      throw error;
    }
  }

  async updateCostLimit(
    userId: string,
    costLimit: number | null,
    resetFrequency?: ResetFrequency,
  ): Promise<void> {
    try {
      await axios.put(`${API_BASE_URL}/settings/users/${userId}/cost-limit`, {
        cost_limit: costLimit,
        reset_frequency: resetFrequency ?? null,
      });
    } catch (error) {
      log.error({ err: error }, 'failed to update cost limit');
      throw error;
    }
  }

  /**
   * Hard-reset a user's running spend tally to $0 without waiting for
   * the time-based weekly / monthly tick. Returns the prior period_spend
   * so the UI can show "reset $11.06" in the toast.
   */
  async resetCostPeriod(
    userId: string,
  ): Promise<{
    cost_limit: number | null;
    reset_frequency: ResetFrequency;
    period_spend: number;
    period_start: string | null;
    prior_period_spend: number;
  }> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/settings/users/${userId}/cost-limit/reset`,
      );
      return response.data;
    } catch (error) {
      log.error({ err: error }, 'failed to reset cost period');
      throw error;
    }
  }

  /**
   * Read the env-configured default spending-limit values + how many
   * existing users have no limit set + the standardized reset anchor
   * (timezone, day-of-week, hour). Drives both the "Apply default to
   * unlimited users" banner and the "Realign spending periods" action.
   */
  async getDefaultCostLimit(): Promise<{
    default_limit: number | null;
    default_frequency: ResetFrequency;
    unlimited_count: number;
    opted_out: boolean;
    anchor?: {
      tz: string;
      hour: number;
      weekday: number;
      weekday_name: string;
      monthly_day: number;
      weekly_label: string;
      daily_label: string;
      monthly_label: string;
    };
    users_with_frequency?: number;
  }> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/settings/users/default-cost-limit`,
      );
      return response.data;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch default cost limit');
      throw error;
    }
  }

  /**
   * Apply the env-configured default spending limit to every user
   * currently without one. Idempotent — running it twice in a row
   * just skips everyone. Returns counts so the UI can show
   * "Applied to N users".
   */
  async applyDefaultCostLimit(): Promise<{
    updated: number;
    skipped: number;
    default_limit: number | null;
    default_frequency: ResetFrequency;
    opted_out: boolean;
  }> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/settings/users/apply-default-cost-limit`,
      );
      return response.data;
    } catch (error) {
      log.error({ err: error }, 'failed to apply default cost limit');
      throw error;
    }
  }

  /**
   * Realign every user's spending period to the standardized anchor
   * schedule (default: every Sunday 09:00 Asia/Kolkata). Zeroes
   * period_spend and rewrites period_start to the most recent anchor
   * boundary. Idempotent.
   */
  async realignSpendingPeriods(): Promise<{
    updated: number;
    skipped: number;
    anchor: {
      tz: string;
      hour: number;
      weekday_name: string;
      weekly_label: string;
      [key: string]: unknown;
    };
  }> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/settings/users/realign-spending-periods`,
      );
      return response.data;
    } catch (error) {
      log.error({ err: error }, 'failed to realign spending periods');
      throw error;
    }
  }

  async getMyUsage(): Promise<UserUsage | null> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/users/me/usage`);
      return response.data.usage;
    } catch (error) {
      log.error({ err: error }, 'failed to fetch usage');
      return null;
    }
  }
}

// Permission types for per-user feature gating
interface PermissionCategory {
  enabled: boolean;
  items: Record<string, boolean>;
}

export interface UserPermissions {
  document_sources: PermissionCategory;
  data_sources: PermissionCategory;
  studio: PermissionCategory;
  integrations: PermissionCategory;
  chat_features: PermissionCategory;
}

export const usersAPI = new UsersAPI();

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
      log.error({ err: error }, 'failed to fetch processing settings');
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
      log.error({ err: error }, 'failed to update processing settings');
      throw error;
    }
  }
}

export const processingSettingsAPI = new ProcessingSettingsAPI();

// ============================================================================
// Model Settings Types and API
// ============================================================================

export interface ModelPricing {
  input_per_mtok: number;
  output_per_mtok: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  description: string;
  pricing: ModelPricing;
}

export interface ModelCategory {
  id: string;
  label: string;
  description: string;
  env_var: string;
}

// { chat: "claude-opus-4-7" | null, studio: ..., query: ..., extraction: ... }
export type ModelSettings = Record<string, string | null>;

// { chat: { "claude-sonnet-4-6": ["default"], "claude-haiku-4-5-20251001": ["chat_naming", "memory"] }, ... }
// Shows which JSON-baked model each prompt uses by default. Lets the UI
// explain what selecting "Default" actually means per category.
export type ModelDefaults = Record<string, Record<string, string[]>>;

export interface ModelSettingsResponse {
  settings: ModelSettings;
  available_models: ModelInfo[];
  categories: ModelCategory[];
  defaults: ModelDefaults;
}

class ModelSettingsAPI {
  /**
   * Get current per-category model overrides plus the lists needed to
   * render the admin UI.
   */
  async getSettings(): Promise<ModelSettingsResponse> {
    try {
      const response = await axios.get(`${API_BASE_URL}/settings/models`);
      return {
        settings: response.data.settings,
        available_models: response.data.available_models,
        categories: response.data.categories,
        defaults: response.data.defaults,
      };
    } catch (error) {
      log.error({ err: error }, 'failed to fetch model settings');
      throw error;
    }
  }

  /**
   * Update per-category model overrides. Pass a partial map — only
   * categories you include are changed. Use null to clear an override
   * (reverts that category to "Default" which uses each prompt's own model).
   */
  async updateSettings(settings: ModelSettings): Promise<ModelSettings> {
    try {
      const response = await axios.post(`${API_BASE_URL}/settings/models`, settings);
      return response.data.settings;
    } catch (error) {
      log.error({ err: error }, 'failed to update model settings');
      throw error;
    }
  }
}

export const modelSettingsAPI = new ModelSettingsAPI();

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
      log.error({ err: error }, 'failed to fetch Google status');
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
      log.error({ err: error }, 'failed to get Google auth URL');
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
      log.error({ err: error }, 'failed to disconnect Google');
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
      log.error({ err: error }, 'failed to list Google files');
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
      log.error({ err: error }, 'failed to import from Google Drive');
      return {
        success: false,
        error: 'Failed to import file',
      };
    }
  }
}

export const googleDriveAPI = new GoogleDriveAPI();
