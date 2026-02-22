/**
 * GoogleDriveTab Component
 * Educational Note: Tab content for importing files from Google Drive.
 * Shows file browser when connected, or setup instructions when not.
 * Features: folder navigation, pagination (Load More), client-side search.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ScrollArea } from '../ui/scroll-area';
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
  GoogleDriveLogo,
  ArrowLeft,
  CircleNotch,
  Gear,
  MagnifyingGlass,
} from '@phosphor-icons/react';
import { googleDriveAPI, type GoogleFile, type GoogleStatus } from '@/lib/api/settings';
import { useToast } from '../ui/toast';
import { DriveItem } from './drive';
import { createLogger } from '@/lib/logger';

const log = createLogger('google-drive-tab');

interface GoogleDriveTabProps {
  projectId: string;
  onImportComplete: () => void;
  isAtLimit: boolean;
}

export const GoogleDriveTab: React.FC<GoogleDriveTabProps> = ({
  projectId,
  onImportComplete,
  isAtLimit,
}) => {
  // Connection status
  const [status, setStatus] = useState<GoogleStatus>({
    configured: false,
    connected: false,
    email: null,
  });

  // Files state
  const [files, setFiles] = useState<GoogleFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);

  // Search state (client-side filtering)
  const [searchQuery, setSearchQuery] = useState('');

  // Navigation state
  const [folderStack, setFolderStack] = useState<{ id: string | null; name: string }[]>([
    { id: null, name: 'My Drive' },
  ]);

  // Import state
  const [importing, setImporting] = useState<string | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<GoogleFile | null>(null);

  const { success, error } = useToast();

  // Load Google status on mount
  useEffect(() => {
    loadStatus();
  }, []);

  // Load files when connected or folder changes
  useEffect(() => {
    if (status.connected) {
      loadFiles(true);
      setSearchQuery(''); // Reset search when changing folders
    }
  }, [status.connected, folderStack]);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const googleStatus = await googleDriveAPI.getStatus();
      setStatus(googleStatus);
    } catch (err) {
      log.error({ err }, 'failed to Lloading Google statusE');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load files from Google Drive
   * Educational Note: freshLoad=true resets the list, false appends (pagination)
   */
  const loadFiles = useCallback(async (freshLoad: boolean = true) => {
    if (freshLoad) {
      setLoading(true);
      setFiles([]);
      setNextPageToken(null);
    } else {
      setLoadingMore(true);
    }

    try {
      const currentFolder = folderStack[folderStack.length - 1];
      const result = await googleDriveAPI.listFiles(
        currentFolder.id || undefined,
        50,
        freshLoad ? undefined : nextPageToken || undefined
      );

      if (result.success) {
        if (freshLoad) {
          setFiles(result.files);
        } else {
          setFiles(prev => [...prev, ...result.files]);
        }
        setNextPageToken(result.next_page_token);
      } else {
        error(result.error || 'Failed to load files');
      }
    } catch (err) {
      log.error({ err }, 'failed to Lloading filesE');
      error('Failed to load Google Drive files');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [folderStack, nextPageToken, error]);

  /**
   * Client-side search filtering
   * Educational Note: Simple case-insensitive name matching
   */
  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return files;
    const query = searchQuery.toLowerCase();
    return files.filter(file => file.name.toLowerCase().includes(query));
  }, [files, searchQuery]);

  const handleFolderClick = (folder: GoogleFile) => {
    setFolderStack([...folderStack, { id: folder.id, name: folder.name }]);
  };

  const handleBack = () => {
    if (folderStack.length > 1) {
      setFolderStack(folderStack.slice(0, -1));
    }
  };

  const handleFileClick = (file: GoogleFile) => {
    if (file.is_folder) {
      handleFolderClick(file);
    } else {
      if (isAtLimit) {
        error('Source limit reached');
        return;
      }
      setSelectedFile(file);
      setConfirmDialogOpen(true);
    }
  };

  const handleConfirmImport = async () => {
    if (!selectedFile) return;

    setConfirmDialogOpen(false);
    setImporting(selectedFile.id);

    try {
      const result = await googleDriveAPI.importFile(projectId, selectedFile.id, selectedFile.name);
      if (result.success) {
        success(`Imported ${selectedFile.name}`);
        onImportComplete();
      } else {
        error(result.error || 'Failed to import file');
      }
    } catch (err) {
      log.error({ err }, 'failed to Limporting fileE');
      error('Failed to import file');
    } finally {
      setImporting(null);
      setSelectedFile(null);
    }
  };

  const handleLoadMore = () => {
    loadFiles(false);
  };

  // Not configured state
  if (!loading && !status.configured) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <GoogleDriveLogo size={48} weight="duotone" className="text-muted-foreground mb-4" />
        <h3 className="font-medium mb-2">Google Drive Not Configured</h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-sm">
          Add your Google Client ID and Client Secret in Admin Settings to enable Google Drive
          integration.
        </p>
        <Button variant="soft" size="sm">
          <Gear size={16} className="mr-2" />
          Open Settings
        </Button>
      </div>
    );
  }

  // Not connected state
  if (!loading && !status.connected) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <GoogleDriveLogo size={48} weight="duotone" className="text-primary mb-4" />
        <h3 className="font-medium mb-2">Connect Google Drive</h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-sm">
          Connect your Google account in Admin Settings to import files from Google Drive.
        </p>
        <Button variant="soft" size="sm">
          <Gear size={16} className="mr-2" />
          Open Settings
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header: Back button + Breadcrumb */}
      <div className="flex items-center gap-2">
        {folderStack.length > 1 && (
          <Button variant="soft" size="sm" onClick={handleBack}>
            <ArrowLeft size={16} />
          </Button>
        )}
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          {folderStack.map((folder, i) => (
            <React.Fragment key={folder.id || 'root'}>
              {i > 0 && <span>/</span>}
              <span className={i === folderStack.length - 1 ? 'font-medium text-foreground' : ''}>
                {folder.name}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Search input */}
      <div className="relative">
        <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9 h-9"
        />
      </div>

      {/* File browser */}
      <ScrollArea className="h-[300px] border rounded-lg">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <CircleNotch size={24} className="animate-spin text-muted-foreground" />
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <p className="text-sm">
              {searchQuery ? 'No files match your search' : 'No files found'}
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {filteredFiles.map((file) => (
              <DriveItem
                key={file.id}
                file={file}
                isImporting={importing === file.id}
                onClick={handleFileClick}
              />
            ))}

            {/* Load More button - only show if not searching and has more */}
            {!searchQuery && nextPageToken && (
              <div className="p-3">
                <Button
                  variant="soft"
                  size="sm"
                  className="w-full"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? (
                    <>
                      <CircleNotch size={16} className="mr-2 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    'Load More'
                  )}
                </Button>
              </div>
            )}
          </div>
        )}
      </ScrollArea>

      {/* Footer info */}
      <p className="text-xs text-muted-foreground">
        Connected as {status.email}
      </p>

      {/* Import Confirmation Dialog */}
      <AlertDialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Import from Google Drive</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedFile && (
                <>
                  Import <span className="font-medium text-foreground">{selectedFile.name}</span>
                  {selectedFile.is_google_file && selectedFile.export_extension && (
                    <span className="text-muted-foreground">
                      {' '}(will be converted to {selectedFile.export_extension.toUpperCase().replace('.', '')})
                    </span>
                  )}
                  {' '}to your sources?
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSelectedFile(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmImport}>Import</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
