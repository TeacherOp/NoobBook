/**
 * AdViewerModal Component
 * Educational Note: Modal for viewing and downloading ad creatives.
 * Displays image grid with hover download buttons for each creative.
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
import { Image, DownloadSimple, PencilSimple } from '@phosphor-icons/react';
import type { AdJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

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

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
      setEditInput('');
    }
  };

  return (
    <Dialog open={viewingAdJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Image size={20} className="text-green-600" />
            Ad Creatives - {viewingAdJob?.product_name}
          </DialogTitle>
          <DialogDescription>
            {viewingAdJob?.images.length} creative{viewingAdJob?.images.length !== 1 ? 's' : ''} generated for Facebook and Instagram
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 py-4">
          {viewingAdJob?.images.map((image, index) => (
            <div key={index} className="flex flex-col gap-2">
              <div className="relative group rounded-lg overflow-hidden border bg-muted">
                <img
                  src={getAuthUrl(image.url)}
                  alt={`${image.type} creative`}
                  className="w-full h-auto object-cover"
                />
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <Button
                    size="sm"
                    variant="secondary"
                    className="gap-1"
                    onClick={() => {
                      const link = document.createElement('a');
                      link.href = getAuthUrl(image.url);
                      link.download = image.filename;
                      link.click();
                    }}
                  >
                    <DownloadSimple size={14} />
                    Download
                  </Button>
                </div>
              </div>
              <div className="text-center">
                <p className="text-xs font-medium capitalize">{image.type.replace('_', ' ')}</p>
                <p className="text-[10px] text-muted-foreground line-clamp-2">{image.prompt}</p>
              </div>
            </div>
          ))}
        </div>

        {onEdit && (
          <div className="flex gap-2 pt-4 border-t">
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
  );
};
