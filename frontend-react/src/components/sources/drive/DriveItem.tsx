/**
 * DriveItem Component
 * Educational Note: Reusable row component for displaying a Google Drive file or folder.
 * Shows icon, name, metadata (type, size), and handles click events.
 */

import React from 'react';
import {
  Folder,
  File,
  FileDoc,
  FileXls,
  FilePpt,
  FilePdf,
  FileImage,
  FileAudio,
  CircleNotch,
} from '@phosphor-icons/react';
import { type GoogleFile } from '@/lib/api/settings';

interface DriveItemProps {
  file: GoogleFile;
  isImporting: boolean;
  onClick: (file: GoogleFile) => void;
}

/**
 * Get the appropriate icon for a file based on its MIME type
 */
const getFileIcon = (file: GoogleFile) => {
  if (file.is_folder) return <Folder size={20} weight="fill" className="text-primary" />;
  if (file.mime_type.includes('document') || file.google_type === 'Google Doc')
    return <FileDoc size={20} weight="fill" className="text-blue-500" />;
  if (file.mime_type.includes('spreadsheet') || file.google_type === 'Google Sheet')
    return <FileXls size={20} weight="fill" className="text-green-500" />;
  if (file.mime_type.includes('presentation') || file.google_type === 'Google Slides')
    return <FilePpt size={20} weight="fill" className="text-orange-500" />;
  if (file.mime_type.includes('pdf'))
    return <FilePdf size={20} weight="fill" className="text-red-500" />;
  if (file.mime_type.startsWith('image/'))
    return <FileImage size={20} weight="fill" className="text-purple-500" />;
  if (file.mime_type.startsWith('audio/'))
    return <FileAudio size={20} weight="fill" className="text-pink-500" />;
  return <File size={20} weight="fill" className="text-muted-foreground" />;
};

/**
 * Format file size to human readable string
 */
const formatFileSize = (bytes: number | null) => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const DriveItem: React.FC<DriveItemProps> = ({ file, isImporting, onClick }) => {
  return (
    <div
      className={`grid grid-cols-[auto_1fr] items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer transition-colors ${
        isImporting ? 'opacity-50 pointer-events-none' : ''
      }`}
      onClick={() => onClick(file)}
    >
      {/* File/Folder icon */}
      <div className="flex-shrink-0">
        {isImporting ? (
          <CircleNotch size={20} className="animate-spin text-primary" />
        ) : (
          getFileIcon(file)
        )}
      </div>

      {/* File info - truncates properly */}
      <div className="overflow-hidden">
        <p className="text-sm font-medium truncate">{file.name}</p>
        <p className="text-xs text-muted-foreground truncate">
          {file.is_google_file && file.google_type && (
            <span className="mr-2">{file.google_type}</span>
          )}
          {file.size && formatFileSize(file.size)}
        </p>
      </div>
    </div>
  );
};
