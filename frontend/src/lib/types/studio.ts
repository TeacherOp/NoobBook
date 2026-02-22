/**
 * Studio Types (framework-agnostic)
 * Extracted from frontend/src/components/studio/types.ts for use in the API layer.
 */

/**
 * Studio item categories - matches backend enum
 */
export type GenerationCategory = 'learning' | 'business' | 'content';

/**
 * Studio item IDs - matches backend studio_item enum exactly
 */
export type StudioItemId =
  | 'quiz'
  | 'flash_cards'
  | 'audio_overview'
  | 'mind_map'
  | 'business_report'
  | 'marketing_strategy'
  | 'ads_creative'
  | 'prd'
  | 'infographics'
  | 'flow_diagram'
  | 'wireframes'
  | 'presentation'
  | 'blog'
  | 'social'
  | 'website'
  | 'email_templates'
  | 'components'
  | 'video';

/**
 * Studio signal from backend - sent by main chat AI
 * Multiple signals can exist for the same studio_item (different topics).
 */
export interface StudioSignal {
  id: string;
  studio_item: StudioItemId;
  direction: string;
  sources: Array<{
    source_id: string;
    chunk_ids?: string[];
  }>;
  created_at: string;
}
