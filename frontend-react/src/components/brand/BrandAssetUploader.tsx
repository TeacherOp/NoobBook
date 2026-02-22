/**
 * BrandAssetUploader Component
 * Educational Note: File upload component for brand assets with drag-and-drop support.
 */
import React, { useState, useRef, useCallback } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Checkbox } from '../ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { UploadSimple, CircleNotch, X } from '@phosphor-icons/react';
import { cn } from '../../lib/utils';
import { brandAPI, createAssetFormData, type BrandAssetType } from '../../lib/api/brand';
import { createLogger } from '@/lib/logger';

const log = createLogger('brand-asset-uploader');

interface BrandAssetUploaderProps {
  assetType: BrandAssetType;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded: () => void;
  acceptedTypes?: string;
}

export const BrandAssetUploader: React.FC<BrandAssetUploaderProps> = ({
  assetType,
  open,
  onOpenChange,
  onUploaded,
  acceptedTypes = 'image/*',
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetForm = () => {
    setFile(null);
    setName('');
    setDescription('');
    setIsPrimary(false);
    setError(null);
  };

  const handleClose = () => {
    resetForm();
    onOpenChange(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      // Auto-fill name from filename if empty
      if (!name) {
        const nameWithoutExt = selectedFile.name.replace(/\.[^/.]+$/, '');
        setName(nameWithoutExt);
      }
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      setFile(droppedFile);
      if (!name) {
        const nameWithoutExt = droppedFile.name.replace(/\.[^/.]+$/, '');
        setName(nameWithoutExt);
      }
    }
  }, [name]);

  const handleUpload = async () => {
    if (!file || !name.trim()) {
      setError('Please select a file and enter a name');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = createAssetFormData(file, name.trim(), assetType, {
        description: description.trim() || undefined,
        isPrimary,
      });

      const response = await brandAPI.uploadAsset(formData);

      if (response.data.success) {
        onUploaded();
        handleClose();
      } else {
        setError(response.data.error || 'Upload failed');
      }
    } catch (err: unknown) {
      log.error({ err }, 'upload failed');
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const getAssetTypeLabel = () => {
    switch (assetType) {
      case 'logo':
        return 'Logo';
      case 'icon':
        return 'Icon';
      case 'font':
        return 'Font';
      case 'image':
        return 'Image';
      default:
        return 'Asset';
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload {getAssetTypeLabel()}</DialogTitle>
          <DialogDescription>
            Add a new {assetType} to your brand kit
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Drop Zone */}
          <div
            className={cn(
              'border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer',
              isDragging
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-primary/50',
              file && 'border-primary bg-primary/5'
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={acceptedTypes}
              onChange={handleFileChange}
              className="hidden"
            />

            {file ? (
              <div className="flex items-center justify-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                >
                  <X size={16} />
                </Button>
              </div>
            ) : (
              <>
                <UploadSimple size={32} className="mx-auto text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  Drag and drop or click to upload
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {assetType === 'font'
                    ? 'TTF, OTF, WOFF, WOFF2'
                    : 'SVG, PNG, JPG, WebP'}
                </p>
              </>
            )}
          </div>

          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`My ${getAssetTypeLabel()}`}
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              rows={2}
            />
          </div>

          {/* Primary Checkbox */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="isPrimary"
              checked={isPrimary}
              onCheckedChange={(checked) => setIsPrimary(checked === true)}
            />
            <Label htmlFor="isPrimary" className="text-sm font-normal cursor-pointer">
              Set as primary {assetType}
            </Label>
          </div>

          {/* Error Message */}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="soft" onClick={handleClose} disabled={uploading}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={uploading || !file}>
            {uploading ? (
              <>
                <CircleNotch size={16} className="animate-spin mr-2" />
                Uploading...
              </>
            ) : (
              'Upload'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
