/**
 * Studio Types
 * Educational Note: Centralized type definitions for Studio panel.
 * Studio items are activated by signals from the main chat based on context.
 */

import {
  PhFileText,
  PhBrain,
  PhHeadphones,
  PhExam,
  PhCards,
  PhTreeStructure,
  PhChartBar,
  PhTarget,
  PhImage,
  PhArticle,
  PhShareNetwork,
  PhGlobe,
  PhEnvelopeSimple,
  PhCube,
  PhChartPieSlice,
  PhFlowArrow,
  PhLayout,
  PhPresentationChart,
  PhVideoCamera,
} from '@phosphor-icons/vue'
import type { Component } from 'vue'

// Re-export framework-agnostic types from lib
export type { StudioSignal, StudioItemId, GenerationCategory } from '@/lib/types/studio'
import type { StudioItemId, GenerationCategory, StudioSignal } from '@/lib/types/studio'

/**
 * Single generation option configuration
 */
export interface GenerationOption {
  id: StudioItemId
  title: string
  description: string
  icon: Component
  category: GenerationCategory
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
    icon: PhExam,
    category: 'learning',
  },
  {
    id: 'flash_cards',
    title: 'Flash Cards',
    description: 'Memorize key concepts',
    icon: PhCards,
    category: 'learning',
  },
  {
    id: 'audio_overview',
    title: 'Audio Overview',
    description: 'Listen to content summary',
    icon: PhHeadphones,
    category: 'learning',
  },
  {
    id: 'mind_map',
    title: 'Mind Map',
    description: 'Visualize relationships',
    icon: PhTreeStructure,
    category: 'learning',
  },

  // BUSINESS
  {
    id: 'business_report',
    title: 'Business Report',
    description: 'Data insights & metrics',
    icon: PhChartBar,
    category: 'business',
  },
  {
    id: 'marketing_strategy',
    title: 'Marketing Strategy',
    description: 'Growth plans & positioning',
    icon: PhTarget,
    category: 'business',
  },
  {
    id: 'prd',
    title: 'PRD',
    description: 'Product requirements doc',
    icon: PhFileText,
    category: 'business',
  },
  {
    id: 'infographics',
    title: 'Infographics',
    description: 'Visual data storytelling',
    icon: PhChartPieSlice,
    category: 'business',
  },
  {
    id: 'flow_diagram',
    title: 'Flow Diagram',
    description: 'Process & system flows',
    icon: PhFlowArrow,
    category: 'business',
  },
  {
    id: 'wireframes',
    title: 'Wireframes',
    description: 'UI/UX design mockups',
    icon: PhLayout,
    category: 'business',
  },
  {
    id: 'presentation',
    title: 'Presentation',
    description: 'Slide decks & pitches',
    icon: PhPresentationChart,
    category: 'business',
  },

  // CONTENT
  {
    id: 'blog',
    title: 'Blog Post',
    description: 'Long-form articles',
    icon: PhArticle,
    category: 'content',
  },
  {
    id: 'social',
    title: 'Social Posts',
    description: 'LinkedIn/Instagram/X',
    icon: PhShareNetwork,
    category: 'content',
  },
  {
    id: 'website',
    title: 'Website',
    description: 'Landing & product pages',
    icon: PhGlobe,
    category: 'content',
  },
  {
    id: 'email_templates',
    title: 'Email Templates',
    description: 'Marketing & transactional',
    icon: PhEnvelopeSimple,
    category: 'content',
  },
  {
    id: 'components',
    title: 'Components',
    description: 'UI components & patterns',
    icon: PhCube,
    category: 'content',
  },
  {
    id: 'ads_creative',
    title: 'Ads Creative',
    description: 'Instagram/Facebook ads',
    icon: PhImage,
    category: 'content',
  },
  {
    id: 'video',
    title: 'Video',
    description: 'Video scripts & content',
    icon: PhVideoCamera,
    category: 'content',
  },
]

/**
 * Category metadata for section headers
 */
export const categoryMeta: Record<
  GenerationCategory,
  { label: string; icon: Component }
> = {
  learning: { label: 'Learning', icon: PhBrain },
  business: { label: 'Business & Product', icon: PhChartBar },
  content: { label: 'Content', icon: PhArticle },
}

/**
 * Helper to get signals for a specific studio item
 */
export const getSignalsForItem = (
  signals: StudioSignal[],
  itemId: StudioItemId
): StudioSignal[] => {
  return signals.filter((s) => s.studio_item === itemId)
}

/**
 * Helper to check if a studio item is active (has signals)
 */
export const isItemActive = (
  signals: StudioSignal[],
  itemId: StudioItemId
): boolean => {
  return signals.some((s) => s.studio_item === itemId)
}
