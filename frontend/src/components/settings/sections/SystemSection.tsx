/**
 * SystemSection Component
 * Manages processing settings (Anthropic tier).
 */

import React, { useState, useEffect } from 'react';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { CircleNotch } from '@phosphor-icons/react';
import { processingSettingsAPI } from '@/lib/api/settings';
import type { AvailableTier } from '@/lib/api/settings';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';
import { useDevFlag } from '@/hooks/useDevFlag';

const log = createLogger('system-section');

export const SystemSection: React.FC = () => {
  const [availableTiers, setAvailableTiers] = useState<AvailableTier[]>([]);
  const [selectedTier, setSelectedTier] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [tierSaving, setTierSaving] = useState(false);

  const { success, error } = useToast();

  // Dev-only: render the streaming tool-call Activity Feed above each
  // assistant turn. Backend always emits the events; the UI is gated
  // here so non-dev users see the existing reading indicator only.
  // No role check needed — this entire section is admin-only at the
  // AppSettings parent (see AppSettings.tsx 'system' case).
  const [activityFeedEnabled, setActivityFeedEnabled] = useDevFlag(
    'tool_activity_feed',
  );

  useEffect(() => {
    loadProcessingSettings();
  }, []);

  const loadProcessingSettings = async () => {
    setLoading(true);
    try {
      const { settings, available_tiers } = await processingSettingsAPI.getSettings();
      setAvailableTiers(available_tiers);
      setSelectedTier(settings.anthropic_tier);
    } catch (err) {
      log.error({ err }, 'failed to load processing settings');
    } finally {
      setLoading(false);
    }
  };

  const handleTierChange = async (tierValue: string) => {
    const tier = parseInt(tierValue, 10);
    setTierSaving(true);
    try {
      await processingSettingsAPI.updateSettings({ anthropic_tier: tier });
      setSelectedTier(tier);
      success('Processing tier updated');
    } catch (err) {
      log.error({ err }, 'failed to update tier');
      error('Failed to update processing tier');
    } finally {
      setTierSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <CircleNotch size={32} className="animate-spin" />
      </div>
    );
  }

  const currentTier = availableTiers.find(t => t.tier === selectedTier);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">System</h2>
        <p className="text-sm text-muted-foreground">
          Configure processing and performance settings
        </p>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3">Developer Tools</h3>
        <div className="space-y-3 rounded-md border border-stone-200 bg-stone-50/60 p-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <Label
                htmlFor="tool-activity-feed-toggle"
                className="text-sm font-medium"
              >
                Tool-call activity feed
              </Label>
              <p className="text-xs text-muted-foreground max-w-md">
                Renders a live, expandable feed of every tool Claude calls
                during a chat turn — including nested analyzer agents. Useful
                for debugging prompts and tool flows. Stored per-browser; off
                by default.
              </p>
            </div>
            <Switch
              id="tool-activity-feed-toggle"
              checked={activityFeedEnabled}
              onCheckedChange={setActivityFeedEnabled}
              aria-label="Toggle tool-call activity feed"
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3">Processing Settings</h3>
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Anthropic Usage Tier</Label>
              {tierSaving && (
                <CircleNotch size={16} className="animate-spin text-muted-foreground" />
              )}
            </div>
            <Select
              value={selectedTier.toString()}
              onValueChange={handleTierChange}
              disabled={tierSaving}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select tier" />
              </SelectTrigger>
              <SelectContent>
                {availableTiers.map((tier) => (
                  <SelectItem key={tier.tier} value={tier.tier.toString()}>
                    {tier.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {currentTier?.description || 'Controls parallel processing speed for PDF extraction'}
            </p>
            <p className="text-xs text-muted-foreground">
              Workers: {currentTier?.max_workers || 4} |
              Rate: {currentTier?.pages_per_minute || 10} pages/min
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
