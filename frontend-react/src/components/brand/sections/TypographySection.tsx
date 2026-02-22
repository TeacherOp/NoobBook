/**
 * TypographySection Component
 * Educational Note: Manages brand typography configuration (fonts, sizes, weights).
 * Includes font picker dropdowns with popular fonts organized by category.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { CircleNotch, Check } from '@phosphor-icons/react';
import {
  brandAPI,
  type Typography,
  type FontWeight,
  getDefaultTypography,
  POPULAR_FONTS,
  FONT_WEIGHTS,
} from '../../../lib/api/brand';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('brand-typography');

type HeadingLevel = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

export const TypographySection: React.FC = () => {
  const [typography, setTypography] = useState<Typography>(getDefaultTypography());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const { success: showSuccess, error: showError } = useToast();

  const loadTypography = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.getConfig();
      if (response.data.success) {
        // Merge with defaults to handle missing h4, h5, h6 from older configs
        const loadedTypography = response.data.config.typography;
        const defaults = getDefaultTypography();
        setTypography({
          ...defaults,
          ...loadedTypography,
          heading_sizes: {
            ...defaults.heading_sizes,
            ...loadedTypography.heading_sizes,
          },
        });
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load typography');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTypography();
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await brandAPI.updateTypography(typography);
      if (response.data.success) {
        setSaved(true);
        showSuccess('Typography saved');
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      log.error({ err: error }, 'failed to save typography');
      showError('Failed to save typography');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: keyof Omit<Typography, 'heading_sizes'>, value: string) => {
    setTypography((prev) => ({ ...prev, [field]: value }));
  };

  const updateHeadingSize = (level: HeadingLevel, value: string) => {
    setTypography((prev) => ({
      ...prev,
      heading_sizes: { ...prev.heading_sizes, [level]: value },
    }));
  };

  // Group fonts by category for the dropdown
  const fontsByCategory = POPULAR_FONTS.reduce((acc, font) => {
    if (!acc[font.category]) {
      acc[font.category] = [];
    }
    acc[font.category].push(font.name);
    return acc;
  }, {} as Record<string, string[]>);

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
            <h2 className="text-xl font-semibold">Typography</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Configure fonts, weights, and text sizing for your brand.
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
              'Save Typography'
            )}
          </Button>
        </div>
      </div>

      {/* Font Families */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Font Families</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="headingFont">Heading Font</Label>
            <Select
              value={typography.heading_font}
              onValueChange={(value) => updateField('heading_font', value)}
            >
              <SelectTrigger id="headingFont">
                <SelectValue placeholder="Select a font" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(fontsByCategory).map(([category, fonts]) => (
                  <SelectGroup key={category}>
                    <SelectLabel>{category}</SelectLabel>
                    {fonts.map((font) => (
                      <SelectItem key={font} value={font} style={{ fontFamily: font }}>
                        {font}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Used for H1-H6 headings
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bodyFont">Body Font</Label>
            <Select
              value={typography.body_font}
              onValueChange={(value) => updateField('body_font', value)}
            >
              <SelectTrigger id="bodyFont">
                <SelectValue placeholder="Select a font" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(fontsByCategory).map(([category, fonts]) => (
                  <SelectGroup key={category}>
                    <SelectLabel>{category}</SelectLabel>
                    {fonts.map((font) => (
                      <SelectItem key={font} value={font} style={{ fontFamily: font }}>
                        {font}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Used for paragraphs and body text
            </p>
          </div>
        </div>
      </div>

      {/* Font Weights */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Font Weights</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="headingWeight">Heading Weight</Label>
            <Select
              value={typography.heading_weight}
              onValueChange={(value) => updateField('heading_weight', value as FontWeight)}
            >
              <SelectTrigger id="headingWeight">
                <SelectValue placeholder="Select weight" />
              </SelectTrigger>
              <SelectContent>
                {FONT_WEIGHTS.map((weight) => (
                  <SelectItem
                    key={weight.value}
                    value={weight.value}
                    style={{ fontWeight: weight.value }}
                  >
                    {weight.label} ({weight.value})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Weight applied to all headings
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bodyWeight">Body Weight</Label>
            <Select
              value={typography.body_weight}
              onValueChange={(value) => updateField('body_weight', value as FontWeight)}
            >
              <SelectTrigger id="bodyWeight">
                <SelectValue placeholder="Select weight" />
              </SelectTrigger>
              <SelectContent>
                {FONT_WEIGHTS.map((weight) => (
                  <SelectItem
                    key={weight.value}
                    value={weight.value}
                    style={{ fontWeight: weight.value }}
                  >
                    {weight.label} ({weight.value})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Weight applied to body text
            </p>
          </div>
        </div>
      </div>

      {/* Heading Sizes */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Heading Sizes</h3>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] as HeadingLevel[]).map((level) => (
            <div key={level} className="space-y-2">
              <Label htmlFor={`${level}Size`}>{level.toUpperCase()} Size</Label>
              <Input
                id={`${level}Size`}
                value={typography.heading_sizes[level]}
                onChange={(e) => updateHeadingSize(level, e.target.value)}
                placeholder={level === 'h1' ? '2.5rem' : level === 'h2' ? '2rem' : '1.5rem'}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Body Text Settings */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Body Text</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="bodySize">Body Size</Label>
            <Input
              id="bodySize"
              value={typography.body_size}
              onChange={(e) => updateField('body_size', e.target.value)}
              placeholder="1rem"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="lineHeight">Line Height</Label>
            <Input
              id="lineHeight"
              value={typography.line_height}
              onChange={(e) => updateField('line_height', e.target.value)}
              placeholder="1.6"
            />
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Preview</h3>

        <div
          className="space-y-4 p-4 bg-muted/30 rounded-lg"
          style={{ fontFamily: typography.body_font }}
        >
          <h1
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h1,
              fontWeight: typography.heading_weight,
              lineHeight: '1.2',
            }}
          >
            Heading 1
          </h1>
          <h2
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h2,
              fontWeight: typography.heading_weight,
              lineHeight: '1.3',
            }}
          >
            Heading 2
          </h2>
          <h3
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h3,
              fontWeight: typography.heading_weight,
              lineHeight: '1.4',
            }}
          >
            Heading 3
          </h3>
          <h4
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h4,
              fontWeight: typography.heading_weight,
              lineHeight: '1.4',
            }}
          >
            Heading 4
          </h4>
          <h5
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h5,
              fontWeight: typography.heading_weight,
              lineHeight: '1.4',
            }}
          >
            Heading 5
          </h5>
          <h6
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h6,
              fontWeight: typography.heading_weight,
              lineHeight: '1.4',
            }}
          >
            Heading 6
          </h6>
          <p
            style={{
              fontSize: typography.body_size,
              fontWeight: typography.body_weight,
              lineHeight: typography.line_height,
            }}
          >
            This is body text. Lorem ipsum dolor sit amet, consectetur adipiscing
            elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
          </p>
        </div>
      </div>
    </div>
  );
};
