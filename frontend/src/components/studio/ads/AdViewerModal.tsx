/**
 * AdViewerModal Component
 * Educational Note: Modal for viewing and downloading ad creatives.
 * Clicking a thumbnail opens it in a full-size lightbox where the user
 * can decide whether to download.
 */

import React, { useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Image, PencilSimple } from '@phosphor-icons/react';
import type { AdJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import {
  ImageLightbox,
  type LightboxImage,
} from '../shared/ImageLightbox';

interface AdViewerModalProps {
  viewingAdJob: AdJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
}

export const AdViewerModal: React.FC<AdViewerModalProps> = ({
  viewingAdJob,
  onClose,
  onEdit,
}) => {
  const [editInput, setEditInput] = useState('');
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // Pre-build the gallery form ImageLightbox expects (resolved URL, alt,
  // filename, caption) once per render so the shared component stays
  // dumb about our specific image shape. Deps reference the source
  // array directly so the memo doesn't bust on every render of a
  // freshly-defaulted `[]`.
  const sourceImages = viewingAdJob?.images;
  const lightboxImages = useMemo<LightboxImage[]>(
    () =>
      (sourceImages ?? []).map((img) => ({
        url: getAuthUrl(img.url),
        alt: `${img.type} creative`,
        filename: img.filename,
        caption: img.type.replace('_', ' '),
      })),
    [sourceImages],
  );
  const images = sourceImages ?? [];

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
      setEditInput('');
    }
  };

  return (
    <>
      <Dialog
        open={viewingAdJob !== null}
        onOpenChange={(open) => {
          if (!open) {
            // Clear the lightbox index when the outer modal closes.
            // Without this, the parent flipping `viewingAdJob` to null
            // empties `lightboxImages` via the memo, which makes the
            // lightbox `image` silently become null — Radix dismisses
            // without firing onOpenChange on the inner Dialog, so the
            // index stays at its last value. Opening any future Ad job
            // whose gallery has an element at that stored index would
            // re-open the lightbox without user input.
            setLightboxIndex(null);
            onClose();
          }
        }}
      >
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Image size={20} className="text-green-600" />
              Ad Creatives - {viewingAdJob?.product_name}
            </DialogTitle>
            <DialogDescription>
              {images.length} creative{images.length !== 1 ? 's' : ''} generated for Facebook and Instagram
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 py-4">
            {images.map((image, index) => (
              <div key={index} className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => setLightboxIndex(index)}
                  aria-label={`Open full-size view of ${image.type.replace('_', ' ')} creative`}
                  className="relative group rounded-lg overflow-hidden border bg-muted cursor-zoom-in transition-shadow hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <img
                    src={getAuthUrl(image.url)}
                    alt={`${image.type} creative`}
                    className="w-full h-auto object-cover"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                    <span className="text-white text-xs font-medium tracking-wide bg-black/40 rounded-full px-3 py-1">
                      Click to enlarge
                    </span>
                  </div>
                </button>
                <div className="text-center">
                  <p className="text-xs font-medium capitalize">{image.type.replace('_', ' ')}</p>
                  <p className="text-[10px] text-muted-foreground line-clamp-2">{image.prompt}</p>
                </div>
              </div>
            ))}
          </div>

          {onEdit && (
            <div className="flex gap-2 pt-4 border-t-2 border-orange-200 bg-orange-50/30 px-1 pb-1 rounded-b-lg">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'warmer colors', 'zoom in on product')"
                className="flex-1"
                onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && handleEdit()}
              />
              <Button
                onClick={handleEdit}
                disabled={!editInput.trim()}
                size="sm"
              >
                <PencilSimple size={14} className="mr-1" />
                Edit
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ImageLightbox
        open={lightboxIndex !== null}
        image={lightboxIndex !== null ? lightboxImages[lightboxIndex] ?? null : null}
        images={lightboxImages}
        index={lightboxIndex ?? undefined}
        onIndexChange={setLightboxIndex}
        onClose={() => setLightboxIndex(null)}
      />
    </>
  );
};
