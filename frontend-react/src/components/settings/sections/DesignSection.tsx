/**
 * DesignSection Component
 * Workspace-level brand kit settings with horizontal sub-tabs.
 * YouTube/Notion-style tabbed navigation for Colors, Typography, Logos, etc.
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Palette,
  TextAa,
  Image,
  Diamond,
  BookOpen,
  Sliders,
} from '@phosphor-icons/react';
import {
  ColorsSection,
  TypographySection,
  LogosSection,
  IconsSection,
  GuidelinesSection,
  FeatureSettingsSection,
} from '../../brand/sections';

type DesignTab = 'colors' | 'typography' | 'logos' | 'icons' | 'guidelines' | 'features';

interface TabItem {
  id: DesignTab;
  label: string;
  icon: React.ReactNode;
}

const tabs: TabItem[] = [
  { id: 'colors', label: 'Colors', icon: <Palette size={16} /> },
  { id: 'typography', label: 'Typography', icon: <TextAa size={16} /> },
  { id: 'logos', label: 'Logos', icon: <Image size={16} /> },
  { id: 'icons', label: 'Icons', icon: <Diamond size={16} /> },
  { id: 'guidelines', label: 'Guidelines', icon: <BookOpen size={16} /> },
  { id: 'features', label: 'Features', icon: <Sliders size={16} /> },
];

export const DesignSection: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DesignTab>('colors');

  const renderContent = () => {
    switch (activeTab) {
      case 'colors':
        return <ColorsSection />;
      case 'typography':
        return <TypographySection />;
      case 'logos':
        return <LogosSection />;
      case 'icons':
        return <IconsSection />;
      case 'guidelines':
        return <GuidelinesSection />;
      case 'features':
        return <FeatureSettingsSection />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-stone-900">Design</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Brand kit applied across all projects' studio-generated content.
        </p>
      </div>

      {/* Horizontal tab bar */}
      <div className="border-b border-stone-200">
        <div className="flex gap-1 -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-amber-600 text-amber-700'
                  : 'border-transparent text-stone-500 hover:text-stone-700 hover:border-stone-300'
              )}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div>{renderContent()}</div>
    </div>
  );
};
