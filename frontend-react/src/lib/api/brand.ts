/**
 * Brand API Service
 *
 * Educational Note: This module handles all brand-related API calls including
 * asset management (logos, icons, fonts, images) and configuration (colors,
 * typography, guidelines, voice, feature settings).
 *
 * Brand is a workspace-level (per-user) setting — shared across all projects.
 */

import { api } from './client';

// =============================================================================
// TYPE DEFINITIONS
// =============================================================================

/**
 * Brand Asset Types
 * Educational Note: Assets are the visual components of a brand kit.
 */
export type BrandAssetType = 'logo' | 'icon' | 'font' | 'image';

export interface BrandAsset {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  asset_type: BrandAssetType;
  file_path: string;
  file_name: string;
  mime_type?: string;
  file_size?: number;
  metadata: Record<string, unknown>;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Custom Color Entry
 * Educational Note: Allows brands to define additional colors beyond the standard palette.
 */
export interface CustomColor {
  name: string;
  value: string;
}

/**
 * Color Palette Configuration
 * Educational Note: Defines the core colors used across brand materials.
 */
export interface ColorEnabled {
  primary: boolean;
  secondary: boolean;
  accent: boolean;
  background: boolean;
  text: boolean;
}

export interface ColorPalette {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  text: string;
  enabled?: ColorEnabled;
  custom: CustomColor[];
}

/**
 * Font Weight Options
 * Educational Note: Standard CSS font weight values.
 */
export type FontWeight = '300' | '400' | '500' | '600' | '700' | '800';

/**
 * Typography Configuration
 * Educational Note: Defines font families, weights, and sizing for consistent text styling.
 */
export interface Typography {
  heading_font: string;
  body_font: string;
  heading_weight: FontWeight;
  body_weight: FontWeight;
  heading_sizes: {
    h1: string;
    h2: string;
    h3: string;
    h4: string;
    h5: string;
    h6: string;
  };
  body_size: string;
  line_height: string;
}

/**
 * Popular Font Options
 * Educational Note: Curated list of web-safe and Google Fonts for brand typography.
 */
export const POPULAR_FONTS = [
  // Sans-Serif (Modern, Clean)
  { name: 'Inter', category: 'Sans-Serif' },
  { name: 'Roboto', category: 'Sans-Serif' },
  { name: 'Open Sans', category: 'Sans-Serif' },
  { name: 'Lato', category: 'Sans-Serif' },
  { name: 'Montserrat', category: 'Sans-Serif' },
  { name: 'Poppins', category: 'Sans-Serif' },
  { name: 'Nunito', category: 'Sans-Serif' },
  { name: 'Work Sans', category: 'Sans-Serif' },
  { name: 'DM Sans', category: 'Sans-Serif' },
  { name: 'Plus Jakarta Sans', category: 'Sans-Serif' },
  // Serif (Traditional, Elegant)
  { name: 'Playfair Display', category: 'Serif' },
  { name: 'Merriweather', category: 'Serif' },
  { name: 'Lora', category: 'Serif' },
  { name: 'Source Serif Pro', category: 'Serif' },
  { name: 'PT Serif', category: 'Serif' },
  { name: 'Libre Baskerville', category: 'Serif' },
  // Display (Headlines, Impact)
  { name: 'Oswald', category: 'Display' },
  { name: 'Bebas Neue', category: 'Display' },
  { name: 'Anton', category: 'Display' },
  { name: 'Archivo Black', category: 'Display' },
  // System Fonts
  { name: 'system-ui', category: 'System' },
  { name: 'Arial', category: 'System' },
  { name: 'Helvetica', category: 'System' },
  { name: 'Georgia', category: 'System' },
] as const;

/**
 * Font Weight Options with Labels
 */
export const FONT_WEIGHTS = [
  { value: '300', label: 'Light' },
  { value: '400', label: 'Regular' },
  { value: '500', label: 'Medium' },
  { value: '600', label: 'Semibold' },
  { value: '700', label: 'Bold' },
  { value: '800', label: 'Extra Bold' },
] as const;

/**
 * Spacing Configuration
 * Educational Note: Defines spacing values for consistent layouts.
 */
export interface Spacing {
  base: string;
  small: string;
  large: string;
  section: string;
}

/**
 * Best Practices Configuration
 * Educational Note: Dos and don'ts guide the AI on brand-appropriate content.
 */
export interface BestPractices {
  dos: string[];
  donts: string[];
}

/**
 * Brand Voice Configuration
 * Educational Note: Defines how the brand "sounds" in communications.
 */
export interface BrandVoice {
  tone: string;
  personality: string[];
  keywords: string[];
}

/**
 * Feature Settings
 * Educational Note: Controls which studio features should apply brand guidelines.
 */
export interface FeatureSettings {
  chat: boolean;
  infographic: boolean;
  presentation: boolean;
  mind_map: boolean;
  blog: boolean;
  email: boolean;
  ads_creative: boolean;
  social_post: boolean;
  prd: boolean;
  business_report: boolean;
  [key: string]: boolean; // Allow additional features
}

/**
 * Full Brand Configuration
 * Educational Note: Complete brand settings stored per user (workspace-level).
 */
export interface BrandConfig {
  id: string;
  user_id: string;
  colors: ColorPalette;
  typography: Typography;
  spacing: Spacing;
  guidelines?: string;
  best_practices: BestPractices;
  voice: BrandVoice;
  feature_settings: FeatureSettings;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// API RESPONSE TYPES
// =============================================================================

interface AssetsResponse {
  success: boolean;
  assets: BrandAsset[];
  count: number;
  error?: string;
}

interface AssetResponse {
  success: boolean;
  asset: BrandAsset;
  message?: string;
  error?: string;
}

interface ConfigResponse {
  success: boolean;
  config: BrandConfig;
  message?: string;
  error?: string;
}

interface SuccessResponse {
  success: boolean;
  message?: string;
  error?: string;
}

// =============================================================================
// API METHODS
// =============================================================================

export const brandAPI = {
  // =========================================================================
  // ASSETS
  // =========================================================================

  /**
   * List all brand assets for the authenticated user
   * @param assetType - Optional filter by asset type
   */
  listAssets: (assetType?: BrandAssetType) => {
    const params = assetType ? { type: assetType } : {};
    return api.get<AssetsResponse>('/brand/assets', { params });
  },

  /**
   * Upload a new brand asset
   * @param formData - FormData with file and metadata
   *
   * Educational Note: We use FormData for file uploads (multipart/form-data)
   * instead of JSON. The FormData should include:
   * - file: The actual file
   * - name: Display name
   * - asset_type: logo|icon|font|image
   * - description: Optional description
   * - is_primary: 'true' or 'false'
   */
  uploadAsset: (formData: FormData) =>
    api.post<AssetResponse>('/brand/assets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),

  /**
   * Get a single brand asset's metadata
   */
  getAsset: (assetId: string) =>
    api.get<AssetResponse>(`/brand/assets/${assetId}`),

  /**
   * Update a brand asset's metadata (not the file)
   */
  updateAsset: (
    assetId: string,
    data: Partial<Pick<BrandAsset, 'name' | 'description' | 'metadata' | 'is_primary'>>
  ) => api.put<AssetResponse>(`/brand/assets/${assetId}`, data),

  /**
   * Delete a brand asset
   */
  deleteAsset: (assetId: string) =>
    api.delete<SuccessResponse>(`/brand/assets/${assetId}`),

  /**
   * Set an asset as the primary for its type
   */
  setAssetPrimary: (assetId: string) =>
    api.post<SuccessResponse>(`/brand/assets/${assetId}/primary`),

  // =========================================================================
  // CONFIGURATION
  // =========================================================================

  /**
   * Get the brand configuration for the authenticated user
   * Educational Note: Creates default config if none exists
   */
  getConfig: () =>
    api.get<ConfigResponse>('/brand/config'),

  /**
   * Update the brand configuration (full or partial)
   */
  updateConfig: (config: Partial<Omit<BrandConfig, 'id' | 'user_id' | 'created_at' | 'updated_at'>>) =>
    api.put<ConfigResponse>('/brand/config', config),

  /**
   * Update just the color palette
   */
  updateColors: (colors: ColorPalette) =>
    api.put<ConfigResponse>('/brand/config/colors', { colors }),

  /**
   * Update just the typography settings
   */
  updateTypography: (typography: Typography) =>
    api.put<ConfigResponse>('/brand/config/typography', { typography }),

  /**
   * Update just the brand guidelines text
   */
  updateGuidelines: (guidelines: string) =>
    api.put<ConfigResponse>('/brand/config/guidelines', { guidelines }),

  /**
   * Update just the brand voice settings
   */
  updateVoice: (voice: BrandVoice) =>
    api.put<ConfigResponse>('/brand/config/voice', { voice }),

  /**
   * Update per-feature brand application settings
   */
  updateFeatureSettings: (featureSettings: FeatureSettings) =>
    api.put<ConfigResponse>('/brand/config/features', { feature_settings: featureSettings }),
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Create a FormData object for asset upload
 * Educational Note: Helper to simplify the upload process
 */
export function createAssetFormData(
  file: File,
  name: string,
  assetType: BrandAssetType,
  options?: {
    description?: string;
    isPrimary?: boolean;
  }
): FormData {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  formData.append('asset_type', assetType);

  if (options?.description) {
    formData.append('description', options.description);
  }

  if (options?.isPrimary) {
    formData.append('is_primary', 'true');
  }

  return formData;
}

/**
 * Get default color palette
 */
export function getDefaultColors(): ColorPalette {
  return {
    primary: '#000000',
    secondary: '#666666',
    accent: '#0066CC',
    background: '#FFFFFF',
    text: '#1A1A1A',
    enabled: { primary: true, secondary: true, accent: true, background: true, text: true },
    custom: []
  };
}

export function getDefaultColorEnabled(): ColorEnabled {
  return { primary: true, secondary: true, accent: true, background: true, text: true };
}

/**
 * Get default typography settings
 */
export function getDefaultTypography(): Typography {
  return {
    heading_font: 'Inter',
    body_font: 'Inter',
    heading_weight: '700',
    body_weight: '400',
    heading_sizes: {
      h1: '2.5rem',
      h2: '2rem',
      h3: '1.5rem',
      h4: '1.25rem',
      h5: '1.125rem',
      h6: '1rem'
    },
    body_size: '1rem',
    line_height: '1.6'
  };
}

/**
 * Get default feature settings
 */
export function getDefaultFeatureSettings(): FeatureSettings {
  return {
    chat: true,
    infographic: true,
    presentation: true,
    mind_map: false,
    blog: true,
    email: true,
    ads_creative: true,
    social_post: true,
    prd: false,
    business_report: true
  };
}
