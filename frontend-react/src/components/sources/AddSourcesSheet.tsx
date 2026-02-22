/**
 * AddSourcesSheet Component
 * Educational Note: Sheet modal with tabs for different source upload methods.
 * Orchestrates UploadTab, LinkTab, and PasteTab components.
 */

import React from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { UploadTab } from './UploadTab';
import { LinkTab } from './LinkTab';
import { PasteTab } from './PasteTab';
import { GoogleDriveTab } from './GoogleDriveTab';
import { ResearchTab } from './ResearchTab';
import { DatabaseTab } from './DatabaseTab';
import { MAX_SOURCES } from '../../lib/api/sources';

interface AddSourcesSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  sourcesCount: number;
  onUpload: (files: FileList | File[]) => Promise<void>;
  onAddUrl: (url: string) => Promise<void>;
  onAddText: (content: string, name: string) => Promise<void>;
  onAddResearch: (topic: string, description: string, links: string[]) => Promise<void>;
  onAddDatabase: (connectionId: string, name?: string, description?: string) => Promise<void>;
  onImportComplete: () => void;
  uploading: boolean;
}

export const AddSourcesSheet: React.FC<AddSourcesSheetProps> = ({
  open,
  onOpenChange,
  projectId,
  sourcesCount,
  onUpload,
  onAddUrl,
  onAddText,
  onAddResearch,
  onAddDatabase,
  onImportComplete,
  uploading,
}) => {
  const isAtLimit = sourcesCount >= MAX_SOURCES;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[500px] sm:w-[600px]">
        <SheetHeader>
          <SheetTitle>Add sources</SheetTitle>
        </SheetHeader>

        <div className="mt-6">
          <p className="text-sm text-muted-foreground mb-4">
            Sources let NoobBook base its responses on the information that
            matters most to you. ({sourcesCount}/{MAX_SOURCES} used)
          </p>

          <Tabs defaultValue="upload" className="w-full">
            <TabsList className="w-full h-auto flex flex-wrap gap-2 bg-transparent p-0">
              <TabsTrigger
                value="upload"
                className="px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white"
              >
                Upload
              </TabsTrigger>
              <TabsTrigger
                value="link"
                className="px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white"
              >
                Link
              </TabsTrigger>
              <TabsTrigger
                value="paste"
                className="px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white"
              >
                Paste
              </TabsTrigger>
              <TabsTrigger
                value="drive"
                className="px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white"
              >
                Drive
              </TabsTrigger>
              <TabsTrigger
                value="research"
                className="px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white"
              >
                Research
              </TabsTrigger>
              <TabsTrigger
                value="database"
                className="px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white"
              >
                Database
              </TabsTrigger>
            </TabsList>

            <TabsContent value="upload" className="mt-6">
              <UploadTab
                onUpload={onUpload}
                uploading={uploading}
                isAtLimit={isAtLimit}
              />
            </TabsContent>

            <TabsContent value="link" className="mt-6">
              <LinkTab onAddUrl={onAddUrl} isAtLimit={isAtLimit} />
            </TabsContent>

            <TabsContent value="paste" className="mt-6">
              <PasteTab onAddText={onAddText} isAtLimit={isAtLimit} />
            </TabsContent>

            <TabsContent value="drive" className="mt-6">
              <GoogleDriveTab
                projectId={projectId}
                onImportComplete={() => {
                  onImportComplete();
                  onOpenChange(false); // Close sheet after import
                }}
                isAtLimit={isAtLimit}
              />
            </TabsContent>

            <TabsContent value="research" className="mt-6">
              <ResearchTab
                onAddResearch={onAddResearch}
                isAtLimit={isAtLimit}
              />
            </TabsContent>

            <TabsContent value="database" className="mt-6">
              <DatabaseTab
                isAtLimit={isAtLimit}
                onAddDatabase={async (connectionId, name, description) => {
                  await onAddDatabase(connectionId, name, description);
                  onImportComplete();
                  onOpenChange(false);
                }}
              />
            </TabsContent>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
};
