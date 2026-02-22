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
import { CircleNotch } from '@phosphor-icons/react';
import { processingSettingsAPI } from '@/lib/api/settings';
import type { AvailableTier } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('system-section');

export const SystemSection: React.FC = () => {
  const [availableTiers, setAvailableTiers] = useState<AvailableTier[]>([]);
  const [selectedTier, setSelectedTier] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [tierSaving, setTierSaving] = useState(false);

  const { success, error } = useToast();

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
