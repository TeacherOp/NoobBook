/**
 * InfographicViewerModal Component
 * Educational Note: Modal for viewing and downloading infographics.
 * Displays full-size image with hover download, key sections, and source info.
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ChartPieSlice, PencilSimple } from '@phosphor-icons/react';
import type { InfographicJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import { ImageLightbox, type LightboxImage } from '../shared/ImageLightbox';

interface InfographicViewerModalProps {
  viewingInfographicJob: InfographicJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

const InfographicEditBar: React.FC<{
  defaultValue: string;
  isGenerating?: boolean;
  onEdit: (instructions: string) => void;
}> = ({ defaultValue, isGenerating, onEdit }) => {
  const [editInput, setEditInput] = useState(defaultValue);

  const handleEdit = () => {
    const trimmed = editInput.trim();
    if (!trimmed || isGenerating) return;
    onEdit(trimmed);
  };

  return (
    <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
      <div className="flex gap-2">
        <Input
          value={editInput}
          onChange={(e) => setEditInput(e.target.value)}
          placeholder="Describe changes... (e.g., 'use darker colors', 'add more data points')"
          className="flex-1"
          disabled={isGenerating}
          onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && !isGenerating && onEdit(editInput.trim())}
        />
        <Button
          onClick={handleEdit}
          disabled={!editInput.trim() || isGenerating}
          size="sm"
        >
          <PencilSimple size={14} className="mr-1" />
          Edit
        </Button>
      </div>
    </div>
  );
};

export const InfographicViewerModal: React.FC<InfographicViewerModalProps> = ({
  viewingInfographicJob,
  onClose,
  onEdit,
  isGenerating,
  defaultEditInput,
}) => {
  // Keep the lightbox state as a single nullable LightboxImage (same
  // shape as Blog / BusinessReport). Deriving `image` from the parent
  // prop while keeping `open` as a separate boolean would let the two
  // diverge: if the parent closes the infographic modal while the
  // lightbox is up, ImageLightbox silently dismisses (because its open
  // condition becomes false) without ever firing onClose, leaving the
  // open flag true — and the next infographic job auto-opens the
  // lightbox without user input.
  const [lightboxImage, setLightboxImage] = useState<LightboxImage | null>(null);

  return (
   <>
    <Dialog
      open={viewingInfographicJob !== null}
      onOpenChange={(open) => {
        if (!open) {
          // ImageLightbox is mounted as a sibling fragment, so the
          // parent closing doesn't tear it down on its own. Clear
          // lightboxImage explicitly so the enlarged view doesn't
          // outlive the infographic modal it was opened from.
          setLightboxImage(null);
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ChartPieSlice size={20} className="text-amber-600" />
            {viewingInfographicJob?.topic_title || 'Infographic'}
            {viewingInfographicJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-orange-600 bg-orange-500/10 px-1.5 py-0.5 rounded">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
          </DialogTitle>
          {viewingInfographicJob?.topic_summary && (
            <DialogDescription>
              {viewingInfographicJob.topic_summary}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Infographic Image */}
        {viewingInfographicJob?.image_url && (
          <div className="py-4">
            <button
              type="button"
              onClick={() => setLightboxImage({
                url: getAuthUrl(viewingInfographicJob.image_url!),
                alt: viewingInfographicJob.topic_title || 'Infographic',
                filename: viewingInfographicJob.image?.filename,
                caption: viewingInfographicJob.topic_title || undefined,
              })}
              aria-label={`Open full-size view of ${viewingInfographicJob.topic_title || 'infographic'}`}
              className="relative group rounded-lg overflow-hidden border bg-muted cursor-zoom-in transition-shadow hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-amber-500 w-full text-left"
            >
              <img
                src={getAuthUrl(viewingInfographicJob.image_url)}
                alt={viewingInfographicJob.topic_title || 'Infographic'}
                className="w-full h-auto object-contain"
              />
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                <span className="text-white text-xs font-medium tracking-wide bg-black/40 rounded-full px-3 py-1">
                  Click to enlarge
                </span>
              </div>
            </button>

            {/* Key Sections */}
            {viewingInfographicJob.key_sections && viewingInfographicJob.key_sections.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">Key Sections</h4>
                <div className="flex flex-wrap gap-2">
                  {viewingInfographicJob.key_sections.map((section, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded text-xs"
                    >
                      {section.title}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Source info */}
            <p className="text-xs text-muted-foreground mt-4">
              Generated from: {viewingInfographicJob.source_name}
            </p>
          </div>
        )}

        {/* Edit input section */}
        {onEdit && (
          <InfographicEditBar
            key={`${viewingInfographicJob?.id || 'infographic-edit'}:${defaultEditInput || ''}`}
            defaultValue={defaultEditInput || ''}
            isGenerating={isGenerating}
            onEdit={onEdit}
          />
        )}
      </DialogContent>
    </Dialog>

    <ImageLightbox
      open={lightboxImage !== null}
      image={lightboxImage}
      onClose={() => setLightboxImage(null)}
    />
   </>
  );
};
