/**
 * ImageLightbox — shared full-size image viewer for Studio outputs.
 *
 * Used by every Studio viewer that shows generated images (Ad creatives,
 * Infographics, Social posts, Blog / Business-report inline charts).
 * Clicking a thumbnail opens the lightbox; the lightbox shows the image
 * at the largest size that fits the viewport and surfaces a Download
 * button so the choice to save is explicit. Optional prev/next nav and
 * left/right arrow keys for galleries.
 */

import React, { useCallback, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { CaretLeft, CaretRight, DownloadSimple } from '@phosphor-icons/react';

export interface LightboxImage {
  /** Resolved (already auth-prefixed) URL. */
  url: string;
  /** Alt text / a11y label. Also used as the visually-hidden DialogTitle. */
  alt?: string;
  /** Filename for the download attribute. If unset, the URL's basename is used. */
  filename?: string;
  /** Optional short label shown next to the Download button. */
  caption?: string;
}

interface ImageLightboxProps {
  /** Whether the lightbox is open. */
  open: boolean;
  /** Active image (or null = closed). */
  image: LightboxImage | null;
  /** Full gallery, used to enable prev/next nav. Single-image callers omit this. */
  images?: LightboxImage[];
  /** Active index into `images`. Ignored if `images` is omitted. */
  index?: number;
  /** Called when the user navigates to a different index via the lightbox. */
  onIndexChange?: (next: number) => void;
  /** Called when the lightbox should close (Esc / backdrop / X). */
  onClose: () => void;
}

const filenameFromUrl = (url: string): string => {
  try {
    const u = new URL(url, window.location.origin);
    const last = u.pathname.split('/').filter(Boolean).pop();
    return last || 'image';
  } catch {
    return 'image';
  }
};

const triggerDownload = (image: LightboxImage) => {
  const link = document.createElement('a');
  link.href = image.url;
  link.download = image.filename || filenameFromUrl(image.url);
  link.click();
};

export const ImageLightbox: React.FC<ImageLightboxProps> = ({
  open,
  image,
  images,
  index,
  onIndexChange,
  onClose,
}) => {
  const galleryLength = images?.length ?? 0;
  const hasGallery = galleryLength > 1 && typeof index === 'number' && !!onIndexChange;

  const showPrev = useCallback(() => {
    if (!hasGallery || index === undefined || !images || !onIndexChange) return;
    onIndexChange((index - 1 + images.length) % images.length);
  }, [hasGallery, index, images, onIndexChange]);

  const showNext = useCallback(() => {
    if (!hasGallery || index === undefined || !images || !onIndexChange) return;
    onIndexChange((index + 1) % images.length);
  }, [hasGallery, index, images, onIndexChange]);

  // Esc is handled by the Dialog itself; we only need arrow-key nav.
  useEffect(() => {
    if (!open || !hasGallery) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') showPrev();
      else if (e.key === 'ArrowRight') showNext();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, hasGallery, showPrev, showNext]);

  return (
    <Dialog open={open && image !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-[95vw] sm:max-w-[90vw] p-3 gap-3">
        <DialogTitle className="sr-only">
          {image?.alt || 'Image preview'}
        </DialogTitle>
        <DialogDescription className="sr-only">
          {hasGallery
            ? 'Use the arrow keys to switch images, or click Download to save the current one.'
            : 'Click Download to save the image.'}
        </DialogDescription>

        {image && (
          <>
            <div className="relative flex items-center justify-center bg-black/5 rounded-md overflow-hidden">
              {hasGallery && (
                <button
                  type="button"
                  onClick={showPrev}
                  aria-label="Previous image"
                  className="absolute left-2 top-1/2 -translate-y-1/2 z-10 rounded-full bg-white/80 hover:bg-white shadow p-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <CaretLeft size={18} />
                </button>
              )}
              <img
                src={image.url}
                alt={image.alt || 'Image preview'}
                className="max-h-[78vh] w-auto object-contain"
              />
              {hasGallery && (
                <button
                  type="button"
                  onClick={showNext}
                  aria-label="Next image"
                  className="absolute right-2 top-1/2 -translate-y-1/2 z-10 rounded-full bg-white/80 hover:bg-white shadow p-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <CaretRight size={18} />
                </button>
              )}
            </div>

            <div className="flex items-center justify-between gap-3 px-1">
              <div className="min-w-0">
                {image.caption && (
                  <p className="text-sm font-medium truncate">{image.caption}</p>
                )}
                {hasGallery && typeof index === 'number' && (
                  <p className="text-xs text-muted-foreground">
                    {index + 1} / {galleryLength}
                  </p>
                )}
              </div>
              <Button
                onClick={() => triggerDownload(image)}
                size="sm"
                className="shrink-0 gap-1"
              >
                <DownloadSimple size={14} />
                Download
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
