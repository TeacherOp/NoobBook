/**
 * FeatureSettingsSection Component
 * Educational Note: Controls which studio features should apply brand guidelines.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Label } from '../../ui/label';
import { Switch } from '../../ui/switch';
import { CircleNotch, Check } from '@phosphor-icons/react';
import { brandAPI, type FeatureSettings, getDefaultFeatureSettings } from '../../../lib/api/brand';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('brand-feature-settings');

interface FeatureConfig {
  key: string;
  label: string;
  description: string;
}

const features: FeatureConfig[] = [
  {
    key: 'chat',
    label: 'Chat',
    description: 'Give the chat AI awareness of your brand colors, voice, and guidelines',
  },
  {
    key: 'infographic',
    label: 'Infographics',
    description: 'Apply brand colors and typography to generated infographics',
  },
  {
    key: 'presentation',
    label: 'Presentations',
    description: 'Use brand styling in generated presentations',
  },
  {
    key: 'mind_map',
    label: 'Mind Maps',
    description: 'Apply brand colors to mind map nodes',
  },
  {
    key: 'blog',
    label: 'Blog Posts',
    description: 'Follow brand voice and tone in blog content',
  },
  {
    key: 'email',
    label: 'Emails',
    description: 'Apply brand voice to email drafts',
  },
  {
    key: 'ads_creative',
    label: 'Ad Creatives',
    description: 'Use brand colors and styling in ad designs',
  },
  {
    key: 'social_post',
    label: 'Social Posts',
    description: 'Follow brand voice in social media content',
  },
  {
    key: 'prd',
    label: 'PRDs',
    description: 'Apply brand terminology in product documents',
  },
  {
    key: 'business_report',
    label: 'Business Reports',
    description: 'Use brand styling in reports and documents',
  },
];

export const FeatureSettingsSection: React.FC = () => {
  const [settings, setSettings] = useState<FeatureSettings>(getDefaultFeatureSettings());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const { success: showSuccess, error: showError } = useToast();

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.getConfig();
      if (response.data.success) {
        setSettings(response.data.config.feature_settings);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await brandAPI.updateFeatureSettings(settings);
      if (response.data.success) {
        setSaved(true);
        showSuccess('Feature settings saved');
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to save settings');
      showError('Failed to save feature settings');
    } finally {
      setSaving(false);
    }
  };

  const toggleFeature = (key: string) => {
    setSettings((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const enableAll = () => {
    const enabled: Record<string, boolean> = {};
    features.forEach((f) => {
      enabled[f.key] = true;
    });
    setSettings(enabled as FeatureSettings);
  };

  const disableAll = () => {
    const disabled: Record<string, boolean> = {};
    features.forEach((f) => {
      disabled[f.key] = false;
    });
    setSettings(disabled as FeatureSettings);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <CircleNotch size={24} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  const enabledCount = features.filter((f) => settings[f.key]).length;

  return (
    <div className="space-y-6">
      {/* Sticky header — stays visible while scrolling within the settings panel */}
      <div className="sticky top-0 z-10 bg-card pb-4 -mx-6 px-6 pt-1 -mt-1">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Feature Settings</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Choose which studio features should apply your brand guidelines.
            </p>
          </div>
          <Button onClick={handleSave} disabled={saving} className="gap-2">
            {saving ? (
              <>
                <CircleNotch size={16} className="animate-spin" />
                Saving...
              </>
            ) : saved ? (
              <>
                <Check size={16} />
                Saved
              </>
            ) : (
              'Save Settings'
            )}
          </Button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex items-center justify-between bg-muted/50 rounded-lg p-4">
        <div>
          <p className="text-sm font-medium">
            {enabledCount} of {features.length} features enabled
          </p>
          <p className="text-xs text-muted-foreground">
            Brand guidelines will be applied to enabled features
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="soft" size="sm" onClick={enableAll}>
            Enable All
          </Button>
          <Button variant="soft" size="sm" onClick={disableAll}>
            Disable All
          </Button>
        </div>
      </div>

      {/* Feature List */}
      <div className="bg-card border rounded-lg divide-y">
        {features.map((feature) => (
          <div
            key={feature.key}
            className="flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
          >
            <div className="space-y-0.5">
              <Label htmlFor={feature.key} className="text-base cursor-pointer">
                {feature.label}
              </Label>
              <p className="text-sm text-muted-foreground">{feature.description}</p>
            </div>
            <Switch
              id={feature.key}
              checked={settings[feature.key] || false}
              onCheckedChange={() => toggleFeature(feature.key)}
            />
          </div>
        ))}
      </div>

      {/* Info Box */}
      <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
        <h4 className="font-medium text-sm mb-2">How it works</h4>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>
            When a feature is enabled, the AI will use your brand colors,
            typography, and voice when generating content.
          </li>
          <li>
            Disabled features will use default styling without brand guidelines.
          </li>
          <li>
            This allows you to selectively apply branding based on the type of
            content being created.
          </li>
        </ul>
      </div>
    </div>
  );
};
