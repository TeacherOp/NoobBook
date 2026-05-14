/**
 * SocialPostViewerModal Component
 * Educational Note: Modal for viewing social posts across multiple platforms.
 * Features: Platform-specific styling, images with download, copy to clipboard.
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
import { ShareNetwork, PencilSimple } from '@phosphor-icons/react';
import { useToast } from '../../ui/use-toast';
import type { SocialPostJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import { copyToClipboard } from '@/lib/clipboard';
import { ImageLightbox, type LightboxImage } from '../shared/ImageLightbox';

interface SocialPostViewerModalProps {
  viewingSocialPostJob: SocialPostJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

const SocialPostEditBar: React.FC<{
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
          placeholder="Describe changes... (e.g., 'make tone more casual', 'add emojis')"
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

export const SocialPostViewerModal: React.FC<SocialPostViewerModalProps> = ({
  viewingSocialPostJob,
  onClose,
  onEdit,
  isGenerating,
  defaultEditInput,
}) => {
  const { success: showSuccess, error: showError } = useToast();
  const postCount = viewingSocialPostJob?.posts.length || 0;

  // Build a lightbox gallery from posts that actually have an image_url.
  // Also precompute a post-index → gallery-index map so the thumbnail
  // click handler can open the lightbox at the right slot in O(1) without
  // re-scanning the post list at render time.
  const { lightboxImages, postIndexToGalleryIndex } = useMemo(() => {
    const images: LightboxImage[] = [];
    const map: Record<number, number> = {};
    viewingSocialPostJob?.posts.forEach((post, postIndex) => {
      if (post.image_url) {
        map[postIndex] = images.length;
        images.push({
          url: getAuthUrl(post.image_url),
          alt: `${post.platform} post`,
          filename: post.image?.filename,
          caption: post.platform === 'twitter' ? 'X (Twitter)' : post.platform,
        });
      }
    });
    return { lightboxImages: images, postIndexToGalleryIndex: map };
  }, [viewingSocialPostJob?.posts]);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // Responsive grid: 1 post = centered single col, 2 = 2-col, 3 = 3-col
  const gridClass = postCount === 1
    ? 'grid grid-cols-1 max-w-sm mx-auto gap-6 py-4'
    : postCount === 2
      ? 'grid grid-cols-1 md:grid-cols-2 gap-6 py-4'
      : 'grid grid-cols-1 md:grid-cols-3 gap-6 py-4';

  // Adjust modal width based on post count
  const dialogMaxWidth = postCount === 1 ? 'sm:max-w-lg' : 'sm:max-w-4xl';

  return (
   <>
    <Dialog
      open={viewingSocialPostJob !== null}
      onOpenChange={(open) => {
        if (!open) {
          // Clear the lightbox index when the outer modal closes — same
          // reason as AdViewerModal: the gallery is derived from the
          // parent prop, so a null parent would silently dismiss the
          // lightbox without firing onOpenChange, leaving the index
          // stale and ready to auto-open on the next compatible job.
          setLightboxIndex(null);
          onClose();
        }
      }}
    >
      <DialogContent className={`${dialogMaxWidth} max-h-[90vh] overflow-y-auto flex flex-col`}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShareNetwork size={20} className="text-cyan-600" />
            Social Posts
            {viewingSocialPostJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-orange-600 bg-orange-500/10 px-1.5 py-0.5 rounded">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
          </DialogTitle>
          {viewingSocialPostJob?.topic_summary && (
            <DialogDescription>
              {viewingSocialPostJob.topic_summary}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className={gridClass}>
          {viewingSocialPostJob?.posts.map((post, index) => (
            <div key={index} className="flex flex-col gap-3 border rounded-lg overflow-hidden bg-card">
              {/* Platform Badge */}
              <div className="px-3 py-2 border-b bg-muted/30">
                <span className={`text-xs font-medium uppercase tracking-wide ${
                  post.platform === 'linkedin' ? 'text-blue-600' :
                  post.platform === 'instagram' ? 'text-pink-600' :
                  'text-sky-500'
                }`}>
                  {post.platform === 'twitter' ? 'X (Twitter)' : post.platform}
                </span>
                <span className="text-[10px] text-muted-foreground ml-2">
                  {post.aspect_ratio}
                </span>
              </div>

              {/* Image */}
              {post.image_url && (
                <button
                  type="button"
                  onClick={() => setLightboxIndex(postIndexToGalleryIndex[index] ?? null)}
                  aria-label={`Open full-size view of ${post.platform} post`}
                  className="relative group cursor-zoom-in focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <img
                    src={getAuthUrl(post.image_url)}
                    alt={`${post.platform} post`}
                    className="w-full h-auto object-cover"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                    <span className="text-white text-xs font-medium tracking-wide bg-black/40 rounded-full px-3 py-1">
                      Click to enlarge
                    </span>
                  </div>
                </button>
              )}

              {/* Copy/Caption */}
              <div className="px-3 pb-3 flex-1">
                <p className="text-sm whitespace-pre-line">{post.copy}</p>
                {post.hashtags.length > 0 && (
                  <p className="text-xs text-muted-foreground mt-2">
                    {post.hashtags.join(' ')}
                  </p>
                )}
              </div>

              {/* Copy to clipboard */}
              <div className="px-3 pb-3">
                <Button
                  size="sm"
                  variant="soft"
                  className="w-full text-xs"
                  onClick={async () => {
                    const fullText = `${post.copy}\n\n${post.hashtags.join(' ')}`;
                    const ok = await copyToClipboard(fullText);
                    if (ok) {
                      showSuccess('Copied to clipboard!');
                    } else {
                      showError('Could not copy. Select the text manually.');
                    }
                  }}
                >
                  Copy Caption
                </Button>
              </div>
            </div>
          ))}
        </div>

        {/* Edit input section */}
        {onEdit && (
          <SocialPostEditBar
            key={`${viewingSocialPostJob?.id || 'social-edit'}:${defaultEditInput || ''}`}
            defaultValue={defaultEditInput || ''}
            isGenerating={isGenerating}
            onEdit={onEdit}
          />
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
