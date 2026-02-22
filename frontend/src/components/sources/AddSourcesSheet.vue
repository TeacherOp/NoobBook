<script setup lang="ts">
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { MAX_SOURCES } from '@/lib/api/sources'
import UploadTab from './UploadTab.vue'
import LinkTab from './LinkTab.vue'
import PasteTab from './PasteTab.vue'
import GoogleDriveTab from './GoogleDriveTab.vue'
import ResearchTab from './ResearchTab.vue'
import DatabaseTab from './DatabaseTab.vue'

const props = defineProps<{
  open: boolean
  projectId: string
  sourcesCount: number
  uploading: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  upload: [files: File[]]
  addUrl: [url: string]
  addText: [content: string, name: string]
  addResearch: [topic: string, description: string, links: string[]]
  addDatabase: [connectionId: string, name?: string, description?: string]
  importComplete: []
}>()

const isAtLimit = computed(() => props.sourcesCount >= MAX_SOURCES)

import { computed } from 'vue'

const TAB_CLASS = 'px-4 py-2 rounded-md border border-[#e1e2e2] bg-[#f5f5f5] text-[#2d2d2d] cursor-pointer transition-all hover:bg-[#eaebeb] data-[state=active]:border-primary data-[state=active]:bg-primary data-[state=active]:text-white'
</script>

<template>
  <Sheet :open="props.open" @update:open="emit('update:open', $event)">
    <SheetContent side="left" class="w-[500px] sm:w-[600px]">
      <SheetHeader>
        <SheetTitle>Add sources</SheetTitle>
      </SheetHeader>

      <div class="mt-6">
        <p class="text-sm text-muted-foreground mb-4">
          Sources let NoobBook base its responses on the information that matters most to you.
          ({{ sourcesCount }}/{{ MAX_SOURCES }} used)
        </p>

        <Tabs default-value="upload" class="w-full">
          <TabsList class="w-full h-auto flex flex-wrap gap-2 bg-transparent p-0">
            <TabsTrigger value="upload" :class="TAB_CLASS">Upload</TabsTrigger>
            <TabsTrigger value="link" :class="TAB_CLASS">Link</TabsTrigger>
            <TabsTrigger value="paste" :class="TAB_CLASS">Paste</TabsTrigger>
            <TabsTrigger value="drive" :class="TAB_CLASS">Drive</TabsTrigger>
            <TabsTrigger value="research" :class="TAB_CLASS">Research</TabsTrigger>
            <TabsTrigger value="database" :class="TAB_CLASS">Database</TabsTrigger>
          </TabsList>

          <TabsContent value="upload" class="mt-6">
            <UploadTab
              :uploading="props.uploading"
              :is-at-limit="isAtLimit"
              @upload="emit('upload', $event)"
            />
          </TabsContent>

          <TabsContent value="link" class="mt-6">
            <LinkTab :is-at-limit="isAtLimit" @add-url="emit('addUrl', $event)" />
          </TabsContent>

          <TabsContent value="paste" class="mt-6">
            <PasteTab
              :is-at-limit="isAtLimit"
              @add-text="(content, name) => emit('addText', content, name)"
            />
          </TabsContent>

          <TabsContent value="drive" class="mt-6">
            <GoogleDriveTab
              :project-id="props.projectId"
              :is-at-limit="isAtLimit"
              @import-complete="() => { emit('importComplete'); emit('update:open', false) }"
            />
          </TabsContent>

          <TabsContent value="research" class="mt-6">
            <ResearchTab
              :is-at-limit="isAtLimit"
              @add-research="(t, d, l) => emit('addResearch', t, d, l)"
            />
          </TabsContent>

          <TabsContent value="database" class="mt-6">
            <DatabaseTab
              :is-at-limit="isAtLimit"
              @add-database="(id, name, desc) => { emit('addDatabase', id, name, desc); emit('importComplete'); emit('update:open', false) }"
            />
          </TabsContent>
        </Tabs>
      </div>
    </SheetContent>
  </Sheet>
</template>
