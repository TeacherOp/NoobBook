/**
 * StudioSections Component
 * Educational Note: Renders all studio feature sections.
 * Each section is isolated - only re-renders when its own state changes.
 * This replaces the old StudioGeneratedContent + StudioProgressIndicators + StudioModals pattern.
 */

import React from 'react';

// Import all sections
import { AudioSection } from './AudioSection';
import { QuizSection } from './QuizSection';
import { FlashCardSection } from './FlashCardSection';
import { MindMapSection } from './MindMapSection';
import { AdSection } from './AdSection';
import { SocialSection } from './SocialSection';
import { InfographicSection } from './InfographicSection';
import { EmailSection } from './EmailSection';
import { WebsiteSection } from './WebsiteSection';
import { ComponentSection } from './ComponentSection';
import { VideoSection } from './VideoSection';
import { FlowDiagramSection } from './FlowDiagramSection';
import { WireframeSection } from './WireframeSection';
import { PresentationSection } from './PresentationSection';
import { PRDSection } from './PRDSection';
import { MarketingStrategySection } from './MarketingStrategySection';
import { BlogSection } from './BlogSection';
import { BusinessReportSection } from './BusinessReportSection';

export const StudioSections: React.FC = () => {
  return (
    <>
      {/* Learning Sections */}
      <AudioSection />
      <QuizSection />
      <FlashCardSection />
      <MindMapSection />

      {/* Business Sections */}
      <BusinessReportSection />
      <MarketingStrategySection />
      <PRDSection />
      <InfographicSection />
      <FlowDiagramSection />
      <WireframeSection />
      <PresentationSection />

      {/* Content Sections */}
      <BlogSection />
      <SocialSection />
      <WebsiteSection />
      <EmailSection />
      <ComponentSection />
      <AdSection />
      <VideoSection />
    </>
  );
};
