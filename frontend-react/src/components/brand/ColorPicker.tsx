/**
 * ColorPicker Component
 * Educational Note: Simple color input with hex value display.
 */
import React from 'react';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

interface ColorPickerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  description?: string;
}

export const ColorPicker: React.FC<ColorPickerProps> = ({
  label,
  value,
  onChange,
  description,
}) => {
  const handleColorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  const handleHexChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let hex = e.target.value;
    // Add # if missing
    if (hex && !hex.startsWith('#')) {
      hex = '#' + hex;
    }
    // Validate hex format
    if (/^#[0-9A-Fa-f]{0,6}$/.test(hex)) {
      onChange(hex);
    }
  };

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <div className="flex items-center gap-3">
        <div className="relative">
          <input
            type="color"
            value={value}
            onChange={handleColorChange}
            className="w-12 h-10 rounded-md border cursor-pointer"
            style={{ padding: 0 }}
          />
        </div>
        <Input
          value={value}
          onChange={handleHexChange}
          placeholder="#000000"
          className="flex-1 font-mono text-sm"
          maxLength={7}
        />
        <div
          className="w-10 h-10 rounded-md border"
          style={{ backgroundColor: value }}
        />
      </div>
    </div>
  );
};
