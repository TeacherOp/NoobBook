/**
 * SettingsSidebar Component
 * Notion-style sidebar navigation for Admin Settings.
 */

import React from 'react';
import { User, Users, Key, Plug, Gear, Palette } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export type SettingsSection = 'profile' | 'team' | 'api-keys' | 'integrations' | 'design' | 'system';

interface SettingsSidebarProps {
  activeSection: SettingsSection;
  onSectionChange: (section: SettingsSection) => void;
  isAdmin: boolean;
}

interface SidebarItem {
  id: SettingsSection;
  label: string;
  icon: React.ReactNode;
  category: 'account' | 'workspace';
  adminOnly?: boolean;
}

const sidebarItems: SidebarItem[] = [
  { id: 'profile', label: 'Profile', icon: <User size={18} />, category: 'account' },
  { id: 'team', label: 'Team', icon: <Users size={18} />, category: 'workspace', adminOnly: true },
  { id: 'api-keys', label: 'API Keys', icon: <Key size={18} />, category: 'workspace', adminOnly: true },
  { id: 'integrations', label: 'Integrations', icon: <Plug size={18} />, category: 'workspace' },
  { id: 'design', label: 'Design', icon: <Palette size={18} />, category: 'workspace', adminOnly: true },
  { id: 'system', label: 'System', icon: <Gear size={18} />, category: 'workspace', adminOnly: true },
];

export const SettingsSidebar: React.FC<SettingsSidebarProps> = ({
  activeSection,
  onSectionChange,
  isAdmin,
}) => {
  const accountItems = sidebarItems.filter(item => item.category === 'account');
  const workspaceItems = sidebarItems.filter(item => item.category === 'workspace');

  const renderItem = (item: SidebarItem) => {
    if (item.adminOnly && !isAdmin) return null;

    return (
      <button
        key={item.id}
        onClick={() => onSectionChange(item.id)}
        className={cn(
          'w-full flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors text-left',
          activeSection === item.id
            ? 'bg-amber-100 text-amber-900 font-medium'
            : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
        )}
      >
        {item.icon}
        <span>{item.label}</span>
      </button>
    );
  };

  return (
    <div className="w-56 flex-shrink-0 bg-stone-50 border-r border-stone-200 p-4 space-y-6">
      <div>
        <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider px-3 mb-2">
          Account
        </h4>
        <div className="space-y-1">
          {accountItems.map(renderItem)}
        </div>
      </div>

      <div>
        <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider px-3 mb-2">
          Workspace
        </h4>
        <div className="space-y-1">
          {workspaceItems.map(renderItem)}
        </div>
      </div>
    </div>
  );
};
