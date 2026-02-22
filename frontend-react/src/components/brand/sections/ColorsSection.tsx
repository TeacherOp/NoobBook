/**
 * ColorsSection Component
 * Educational Note: Manages brand color palette configuration.
 * Each color has an enable/disable toggle so users only include
 * the colors they need in generated content.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Switch } from '../../ui/switch';
import { Plus, Trash, CircleNotch, Check } from '@phosphor-icons/react';
import { brandAPI, type ColorPalette, type CustomColor, type ColorEnabled, getDefaultColors, getDefaultColorEnabled } from '../../../lib/api/brand';
import { ColorPicker } from '../ColorPicker';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('brand-colors');

/** The 5 standard brand color slots with display metadata. */
const COLOR_FIELDS: { key: keyof Omit<ColorPalette, 'custom' | 'enabled'>; label: string; description: string }[] = [
  { key: 'primary', label: 'Primary', description: 'Main brand color for buttons and CTAs' },
  { key: 'secondary', label: 'Secondary', description: 'Supporting color for secondary elements' },
  { key: 'accent', label: 'Accent', description: 'Highlight color for emphasis' },
  { key: 'background', label: 'Background', description: 'Page background color' },
  { key: 'text', label: 'Text', description: 'Primary text color' },
];

export const ColorsSection: React.FC = () => {
  const [colors, setColors] = useState<ColorPalette>(getDefaultColors());
  const [enabled, setEnabled] = useState<ColorEnabled>(getDefaultColorEnabled());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newColorName, setNewColorName] = useState('');
  const [newColorValue, setNewColorValue] = useState('#000000');
  const { success: showSuccess, error: showError } = useToast();

  const loadColors = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.getConfig();
      if (response.data.success) {
        const loaded = response.data.config.colors;
        setColors({ ...loaded, custom: loaded.custom ?? [] });
        setEnabled(loaded.enabled ?? getDefaultColorEnabled());
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load colors');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadColors();
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await brandAPI.updateColors({ ...colors, enabled });
      if (response.data.success) {
        setSaved(true);
        showSuccess('Colors saved');
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to save colors');
      showError('Failed to save colors');
    } finally {
      setSaving(false);
    }
  };

  const updateColor = (key: keyof Omit<ColorPalette, 'custom' | 'enabled'>, value: string) => {
    setColors((prev) => ({ ...prev, [key]: value }));
  };

  const toggleColor = (key: keyof ColorEnabled) => {
    setEnabled((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const addCustomColor = () => {
    if (!newColorName.trim()) return;

    setColors((prev) => ({
      ...prev,
      custom: [...prev.custom, { name: newColorName.trim(), value: newColorValue }],
    }));
    setNewColorName('');
    setNewColorValue('#000000');
  };

  const removeCustomColor = (index: number) => {
    setColors((prev) => ({
      ...prev,
      custom: prev.custom.filter((_, i) => i !== index),
    }));
  };

  const updateCustomColor = (index: number, field: keyof CustomColor, value: string) => {
    setColors((prev) => ({
      ...prev,
      custom: prev.custom.map((c, i) =>
        i === index ? { ...c, [field]: value } : c
      ),
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <CircleNotch size={24} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Sticky header — stays visible while scrolling within the settings panel */}
      <div className="sticky top-0 z-10 bg-card pb-4 -mx-6 px-6 pt-1 -mt-1">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Colors</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Define your brand color palette for consistent styling across generated content.
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
              'Save Colors'
            )}
          </Button>
        </div>
      </div>

      {/* Primary Colors */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Primary Colors</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {COLOR_FIELDS.map(({ key, label, description }) => (
            <div key={key} className={!enabled[key] ? 'opacity-40' : undefined}>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-medium">{label}</Label>
                <Switch
                  checked={enabled[key]}
                  onCheckedChange={() => toggleColor(key)}
                  aria-label={`Toggle ${label} color`}
                />
              </div>
              <p className="text-xs text-muted-foreground mb-2">{description}</p>
              <div className={!enabled[key] ? 'pointer-events-none' : undefined}>
                <ColorPicker
                  label=""
                  value={colors[key] as string}
                  onChange={(v) => updateColor(key, v)}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Custom Colors */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Custom Colors</h3>

        {colors.custom.length > 0 && (
          <div className="space-y-4">
            {colors.custom.map((color, index) => (
              <div key={index} className="flex items-end gap-3">
                <div className="flex-1 space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={color.name}
                    onChange={(e) => updateCustomColor(index, 'name', e.target.value)}
                    placeholder="Color name"
                  />
                </div>
                <div className="flex-1">
                  <ColorPicker
                    label="Color"
                    value={color.value}
                    onChange={(v) => updateCustomColor(index, 'value', v)}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-10 w-10 text-destructive hover:text-destructive"
                  onClick={() => removeCustomColor(index)}
                >
                  <Trash size={16} />
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Add Custom Color */}
        <div className="flex items-end gap-3 pt-4 border-t">
          <div className="flex-1 space-y-2">
            <Label>New Color Name</Label>
            <Input
              value={newColorName}
              onChange={(e) => setNewColorName(e.target.value)}
              placeholder="e.g., Brand Red"
            />
          </div>
          <div className="flex-1">
            <ColorPicker
              label="Color Value"
              value={newColorValue}
              onChange={setNewColorValue}
            />
          </div>
          <Button
            variant="soft"
            onClick={addCustomColor}
            disabled={!newColorName.trim()}
            className="gap-2"
          >
            <Plus size={16} />
            Add
          </Button>
        </div>
      </div>

      {/* Preview — only shows enabled colors */}
      <div className="bg-card border rounded-lg p-6 space-y-4">
        <h3 className="font-medium">Preview</h3>
        <div className="flex flex-wrap gap-4">
          {COLOR_FIELDS.filter(({ key }) => enabled[key]).map(({ key, label }) => (
            <div key={key} className="text-center">
              <div
                className="w-16 h-16 rounded-lg border"
                style={{ backgroundColor: colors[key] as string }}
              />
              <p className="text-xs text-muted-foreground mt-1">{label}</p>
            </div>
          ))}
          {colors.custom.map((color, index) => (
            <div key={index} className="text-center">
              <div
                className="w-16 h-16 rounded-lg border"
                style={{ backgroundColor: color.value }}
              />
              <p className="text-xs text-muted-foreground mt-1 truncate max-w-16">
                {color.name}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
