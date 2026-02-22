<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  PhGoogleDriveLogo, PhFolder, PhFileText, PhFile,
  PhArrowLeft, PhCircleNotch, PhArrowClockwise,
} from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { api } from '@/lib/api/client'
import { createLogger } from '@/lib/logger'

const log = createLogger('google-drive-tab')

const props = defineProps<{
  projectId: string
  isAtLimit: boolean
}>()
const emit = defineEmits<{ importComplete: [] }>()

interface DriveFile {
  id: string; name: string; mimeType: string; size?: number
  modifiedTime?: string; parents?: string[]
}

type Status = 'unconfigured' | 'disconnected' | 'connected'

const status = ref<Status>('unconfigured')
const files = ref<DriveFile[]>([])
const loading = ref(false)
const folderId = ref<string | null>(null)
const folderStack = ref<{ id: string; name: string }[]>([])
const searchQuery = ref('')
const nextPageToken = ref<string | null>(null)
const confirmFile = ref<DriveFile | null>(null)
const importing = ref(false)

async function checkStatus() {
  loading.value = true
  try {
    const res = await api.get('/google/status')
    if (!res.data.configured) { status.value = 'unconfigured'; return }
    if (!res.data.connected) { status.value = 'disconnected'; return }
    status.value = 'connected'
    await loadFiles()
  } catch (err) {
    log.error({ err }, 'failed to check Google Drive status')
    status.value = 'unconfigured'
  } finally {
    loading.value = false
  }
}

async function loadFiles(pageToken?: string) {
  loading.value = true
  try {
    const params: Record<string, string> = { page_size: '20' }
    if (folderId.value) params.folder_id = folderId.value
    if (pageToken) params.page_token = pageToken

    const res = await api.get('/google/files', { params })
    if (pageToken) {
      files.value = [...files.value, ...(res.data.files || [])]
    } else {
      files.value = res.data.files || []
    }
    nextPageToken.value = res.data.next_page_token || null
  } catch (err) {
    log.error({ err }, 'failed to load Google Drive files')
  } finally {
    loading.value = false
  }
}

async function connectDrive() {
  try {
    const res = await api.get('/google/auth')
    window.location.href = res.data.auth_url
  } catch (err) {
    log.error({ err }, 'failed to get Google auth URL')
  }
}

async function openFolder(file: DriveFile) {
  folderStack.value.push({ id: folderId.value || 'root', name: folderId.value ? files.value.find(f => f.id === folderId.value)?.name || 'Back' : 'My Drive' })
  folderId.value = file.id
  searchQuery.value = ''
  await loadFiles()
}

async function goBack() {
  const prev = folderStack.value.pop()
  folderId.value = prev?.id === 'root' ? null : (prev?.id || null)
  await loadFiles()
}

async function importFile(file: DriveFile) {
  importing.value = true
  try {
    await api.post(`/projects/${props.projectId}/sources/google-import`, { file_id: file.id, file_name: file.name, mime_type: file.mimeType })
    confirmFile.value = null
    emit('importComplete')
  } catch (err) {
    log.error({ err }, 'failed to import Google Drive file')
  } finally {
    importing.value = false
  }
}

function fileIcon(mimeType: string) {
  if (mimeType === 'application/vnd.google-apps.folder') return PhFolder
  if (mimeType.includes('document')) return PhFileText
  if (mimeType.includes('spreadsheet')) return PhFileText
  if (mimeType.includes('presentation')) return PhFileText
  return PhFile
}

const filteredFiles = computed(() =>
  searchQuery.value
    ? files.value.filter(f => f.name.toLowerCase().includes(searchQuery.value.toLowerCase()))
    : files.value
)

onMounted(checkStatus)

// computed is imported at top-level but used inline — need to import it
import { computed } from 'vue'
</script>

<template>
  <div class="space-y-4">
    <!-- Unconfigured -->
    <div v-if="status === 'unconfigured'" class="text-center py-6 text-sm text-muted-foreground">
      <PhGoogleDriveLogo :size="32" class="mx-auto mb-3 opacity-50" />
      <p>Google Drive is not configured.</p>
      <p class="text-xs mt-1">Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env</p>
    </div>

    <!-- Disconnected -->
    <div v-else-if="status === 'disconnected'" class="text-center py-6 space-y-3">
      <PhGoogleDriveLogo :size="32" class="mx-auto opacity-70" />
      <p class="text-sm">Connect your Google Drive to import files</p>
      <Button @click="connectDrive">Connect Google Drive</Button>
    </div>

    <!-- Connected -->
    <template v-else>
      <!-- Nav + search -->
      <div class="flex items-center gap-2">
        <Button v-if="folderStack.length" variant="ghost" size="icon-sm" @click="goBack">
          <PhArrowLeft :size="16" />
        </Button>
        <Input v-model="searchQuery" placeholder="Search files..." class="flex-1 h-8 text-sm" />
        <Button variant="ghost" size="icon-sm" :disabled="loading" @click="loadFiles()">
          <PhArrowClockwise :size="14" :class="loading ? 'animate-spin' : ''" />
        </Button>
      </div>

      <!-- Breadcrumb -->
      <p v-if="folderStack.length" class="text-xs text-muted-foreground">
        {{ folderStack.map(f => f.name).join(' › ') }}
      </p>

      <!-- File list -->
      <div v-if="loading && !files.length" class="text-center py-4">
        <PhCircleNotch :size="20" class="animate-spin text-muted-foreground mx-auto" />
      </div>
      <div v-else class="space-y-1 max-h-64 overflow-y-auto">
        <div
          v-for="file in filteredFiles"
          :key="file.id"
          class="flex items-center gap-3 p-2 rounded-md hover:bg-muted/50 cursor-pointer text-sm transition-colors"
          @click="file.mimeType === 'application/vnd.google-apps.folder' ? openFolder(file) : confirmFile = file"
        >
          <component :is="fileIcon(file.mimeType)" :size="16" class="text-muted-foreground shrink-0" />
          <span class="flex-1 truncate">{{ file.name }}</span>
        </div>
        <p v-if="filteredFiles.length === 0" class="text-center text-xs text-muted-foreground py-4">
          No files found
        </p>
      </div>

      <!-- Load more -->
      <Button v-if="nextPageToken" variant="ghost" size="sm" class="w-full" :disabled="loading" @click="loadFiles(nextPageToken!)">
        Load more
      </Button>
    </template>

    <!-- Import confirmation dialog -->
    <Dialog :open="!!confirmFile" @update:open="(v) => { if (!v) confirmFile = null }">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Import file</DialogTitle>
          <DialogDescription>
            Import "{{ confirmFile?.name }}" as a source?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="soft" :disabled="importing" @click="confirmFile = null">Cancel</Button>
          <Button :disabled="importing || props.isAtLimit" @click="confirmFile && importFile(confirmFile)">
            <PhCircleNotch v-if="importing" :size="16" class="mr-2 animate-spin" />
            {{ importing ? 'Importing...' : 'Import' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
