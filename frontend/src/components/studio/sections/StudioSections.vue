<script setup lang="ts">
/**
 * StudioSections — renders all 18 studio feature sections.
 * Each section is self-contained and only renders when it has content.
 */
import AudioSection from '../audio/AudioSection.vue'
import BlogSection from './BlogSection.vue'
import QuizSection from './QuizSection.vue'
import FlashCardSection from './FlashCardSection.vue'
import MindMapSection from './MindMapSection.vue'
import PresentationSection from './PresentationSection.vue'
import PRDSection from './PRDSection.vue'
import VideoSection from './VideoSection.vue'
import BusinessReportSection from './BusinessReportSection.vue'
import MarketingStrategySection from './MarketingStrategySection.vue'
import AdSection from './AdSection.vue'
import SocialSection from './SocialSection.vue'
import InfographicSection from './InfographicSection.vue'
import EmailSection from './EmailSection.vue'
import WebsiteSection from './WebsiteSection.vue'
import ComponentSection from './ComponentSection.vue'
import FlowDiagramSection from './FlowDiagramSection.vue'
import WireframeSection from './WireframeSection.vue'
</script>

<template>
  <!-- Learning -->
  <AudioSection />
  <QuizSection />
  <FlashCardSection />
  <MindMapSection />

  <!-- Business -->
  <BusinessReportSection />
  <MarketingStrategySection />
  <PRDSection />
  <InfographicSection />
  <FlowDiagramSection />
  <WireframeSection />
  <PresentationSection />

  <!-- Content -->
  <BlogSection />
  <SocialSection />
  <WebsiteSection />
  <EmailSection />
  <ComponentSection />
  <AdSection />
  <VideoSection />
</template>
