/**
 * BrandAssetCard Component
 * Educational Note: Displays a single brand asset (logo, icon, font, image)
 * with actions for viewing, setting primary, and deleting.
 */
import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import {
  DotsThreeVertical,
  Star,
  Trash,
  DownloadSimple,
  CircleNotch,
} from '@phosphor-icons/react';
import { type BrandAsset } from '../../lib/api/brand';
import { api } from '../../lib/api/client';
import { createLogger } from '@/lib/logger';

const log = createLogger('brand-asset-card');

interface BrandAssetCardProps {
  asset: BrandAsset;
  onDelete: (assetId: string) => void;
  onSetPrimary: (assetId: string) => void;
}

export const BrandAssetCard: React.FC<BrandAssetCardProps> = ({
  asset,
  onDelete,
  onSetPrimary,
}) => {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loadingImage, setLoadingImage] = useState(false);
  const blobUrlRef = useRef<string | null>(null);

  // Build authenticated image URL for preview
  // Educational Note: The download endpoint now proxies the file through the backend
  // (instead of returning a Supabase signed URL) so it works in Docker where the
  // Supabase internal hostname isn't reachable from the browser.
  useEffect(() => {
    const loadImage = async () => {
      if (asset.mime_type?.startsWith('image/')) {
        setLoadingImage(true);
        try {
          const response = await api.get(`/brand/assets/${asset.id}/download`, {
            responseType: 'blob',
          });
          const objectUrl = URL.createObjectURL(response.data);
          blobUrlRef.current = objectUrl;
          setImageUrl(objectUrl);
        } catch (error) {
          log.error({ err: error }, 'failed to load image');
        } finally {
          setLoadingImage(false);
        }
      }
    };
    loadImage();
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [asset.id, asset.mime_type]);

  const handleDownload = async () => {
    try {
      const response = await api.get(`/brand/assets/${asset.id}/download`, {
        responseType: 'blob',
      });
      const blobUrl = URL.createObjectURL(response.data);
      window.open(blobUrl, '_blank');
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (error) {
      log.error({ err: error }, 'failed to download');
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'Unknown size';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <>
      <div className="border rounded-lg bg-card overflow-hidden">
        {/* Image Preview */}
        <div className="aspect-square bg-muted/30 flex items-center justify-center relative">
          {loadingImage ? (
            <CircleNotch size={24} className="animate-spin text-muted-foreground" />
          ) : imageUrl ? (
            <img
              src={imageUrl}
              alt={asset.name}
              className="max-w-full max-h-full object-contain p-4"
            />
          ) : (
            <div className="text-muted-foreground text-sm">
              {asset.asset_type === 'font' ? 'Font File' : 'No Preview'}
            </div>
          )}

          {/* Primary Badge */}
          {asset.is_primary && (
            <Badge
              variant="default"
              className="absolute top-2 left-2 gap-1"
            >
              <Star size={12} weight="fill" />
              Primary
            </Badge>
          )}
        </div>

        {/* Info */}
        <div className="p-3 border-t">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h3 className="font-medium text-sm truncate">{asset.name}</h3>
              <p className="text-xs text-muted-foreground truncate">
                {asset.file_name}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {formatFileSize(asset.file_size)}
              </p>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                  <DotsThreeVertical size={16} />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleDownload}>
                  <DownloadSimple size={16} className="mr-2" />
                  Download
                </DropdownMenuItem>
                {!asset.is_primary && (
                  <DropdownMenuItem onClick={() => onSetPrimary(asset.id)}>
                    <Star size={16} className="mr-2" />
                    Set as Primary
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setDeleteDialogOpen(true)}
                >
                  <Trash size={16} className="mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {asset.description && (
            <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
              {asset.description}
            </p>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Asset</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{asset.name}"? This action cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                onDelete(asset.id);
                setDeleteDialogOpen(false);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
