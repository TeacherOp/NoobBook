/**
 * Studio Types
 * Educational Note: Centralized type definitions for Studio panel.
 * Studio items are activated by signals from the main chat based on context.
 */

import {
  FileText,
  Brain,
  Headphones,
  Exam,
  Cards,
  TreeStructure,
  ChartBar,
  Target,
  Image,
  Article,
  ShareNetwork,
  Globe,
  EnvelopeSimple,
  Cube,
  ChartPieSlice,
  FlowArrow,
  Layout,
  PresentationChart,
  VideoCamera,
} from '@phosphor-icons/react';

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
 * Educational Note: These signals activate studio items contextually.
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

/**
 * Single generation option configuration
 */
export interface GenerationOption {
  id: StudioItemId;
  title: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  category: GenerationCategory;
}

/**
 * All available generation options
 * Educational Note: Organized by category - Learning, Business, Content
 */
export const generationOptions: GenerationOption[] = [
  // LEARNING
  {
    id: 'quiz',
    title: 'Quiz',
    description: 'Test knowledge retention',
    icon: Exam,
    category: 'learning',
  },
  {
    id: 'flash_cards',
    title: 'Flash Cards',
    description: 'Memorize key concepts',
    icon: Cards,
    category: 'learning',
  },
  {
    id: 'audio_overview',
    title: 'Audio Overview',
    description: 'Listen to content summary',
    icon: Headphones,
    category: 'learning',
  },
  {
    id: 'mind_map',
    title: 'Mind Map',
    description: 'Visualize relationships',
    icon: TreeStructure,
    category: 'learning',
  },

  // BUSINESS
  {
    id: 'business_report',
    title: 'Business Report',
    description: 'Data insights & metrics',
    icon: ChartBar,
    category: 'business',
  },
  {
    id: 'marketing_strategy',
    title: 'Marketing Strategy',
    description: 'Growth plans & positioning',
    icon: Target,
    category: 'business',
  },
  {
    id: 'prd',
    title: 'PRD',
    description: 'Product requirements doc',
    icon: FileText,
    category: 'business',
  },
  {
    id: 'infographics',
    title: 'Infographics',
    description: 'Visual data storytelling',
    icon: ChartPieSlice,
    category: 'business',
  },
  {
    id: 'flow_diagram',
    title: 'Flow Diagram',
    description: 'Process & system flows',
    icon: FlowArrow,
    category: 'business',
  },
  {
    id: 'wireframes',
    title: 'Wireframes',
    description: 'UI/UX design mockups',
    icon: Layout,
    category: 'business',
  },
  {
    id: 'presentation',
    title: 'Presentation',
    description: 'Slide decks & pitches',
    icon: PresentationChart,
    category: 'business',
  },

  // CONTENT
  {
    id: 'blog',
    title: 'Blog Post',
    description: 'Long-form articles',
    icon: Article,
    category: 'content',
  },
  {
    id: 'social',
    title: 'Social Posts',
    description: 'LinkedIn/Instagram/X',
    icon: ShareNetwork,
    category: 'content',
  },
  {
    id: 'website',
    title: 'Website',
    description: 'Landing & product pages',
    icon: Globe,
    category: 'content',
  },
  {
    id: 'email_templates',
    title: 'Email Templates',
    description: 'Marketing & transactional',
    icon: EnvelopeSimple,
    category: 'content',
  },
  {
    id: 'components',
    title: 'Components',
    description: 'UI components & patterns',
    icon: Cube,
    category: 'content',
  },
  {
    id: 'ads_creative',
    title: 'Ads Creative',
    description: 'Instagram/Facebook ads',
    icon: Image,
    category: 'content',
  },
  {
    id: 'video',
    title: 'Video',
    description: 'Video scripts & content',
    icon: VideoCamera,
    category: 'content',
  },
];

/**
 * Category metadata for section headers
 */
export const categoryMeta: Record<
  GenerationCategory,
  { label: string; icon: React.ComponentType<{ size?: number; className?: string }> }
> = {
  learning: { label: 'Learning', icon: Brain },
  business: { label: 'Business & Product', icon: ChartBar },
  content: { label: 'Content', icon: Article },
};

/**
 * Helper to get signals for a specific studio item
 */
export const getSignalsForItem = (
  signals: StudioSignal[],
  itemId: StudioItemId
): StudioSignal[] => {
  return signals.filter((s) => s.studio_item === itemId);
};

/**
 * Helper to check if a studio item is active (has signals)
 */
export const isItemActive = (
  signals: StudioSignal[],
  itemId: StudioItemId
): boolean => {
  return signals.some((s) => s.studio_item === itemId);
};
