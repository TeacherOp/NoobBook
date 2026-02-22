<script setup lang="ts">
import { ref } from 'vue'
import { PhUploadSimple, PhCircleNotch, PhWarning } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ALLOWED_EXTENSIONS, MAX_IMAGE_SIZE } from '@/lib/api/sources'

const props = defineProps<{
  uploading: boolean
  isAtLimit: boolean
}>()

const emit = defineEmits<{
  upload: [files: File[]]
}>()

const dragActive = ref(false)
const validationError = ref<string | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const ACCEPTED_FILE_TYPES = Object.values(ALLOWED_EXTENSIONS).flat().join(',')

function validateFiles(files: File[]): string | null {
  for (const file of files) {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (ALLOWED_EXTENSIONS.image.includes(ext) && file.size > MAX_IMAGE_SIZE) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(1)
      return `Image "${file.name}" is too large (${sizeMB}MB). Maximum 5MB per image.`
    }
  }
  return null
}

function handleUpload(files: FileList | File[]) {
  validationError.value = null
  const fileArray = Array.from(files)
  const err = validateFiles(fileArray)
  if (err) { validationError.value = err; return }
  emit('upload', fileArray)
}

function handleDrag(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  dragActive.value = e.type === 'dragenter' || e.type === 'dragover'
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  dragActive.value = false
  if (e.dataTransfer?.files?.length) handleUpload(e.dataTransfer.files)
}

function handleFileInput(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files?.length) handleUpload(files)
}
</script>

<template>
  <div>
    <input
      ref="fileInputRef"
      type="file"
      multiple
      class="hidden"
      :accept="ACCEPTED_FILE_TYPES"
      @change="handleFileInput"
    />

    <div
      class="border-2 border-dashed rounded-lg p-8 text-center transition-colors"
      :class="[
        dragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25',
        props.uploading ? 'opacity-50 pointer-events-none' : ''
      ]"
      @dragenter="handleDrag"
      @dragleave="handleDrag"
      @dragover="handleDrag"
      @drop="handleDrop"
    >
      <template v-if="props.uploading">
        <PhCircleNotch :size="40" class="mx-auto mb-4 text-primary animate-spin" />
        <p class="text-sm font-medium mb-1">Uploading...</p>
      </template>
      <template v-else>
        <PhUploadSimple :size="40" class="mx-auto mb-4 text-muted-foreground" />
        <p class="text-sm font-medium mb-1">Upload sources</p>
        <p class="text-xs text-muted-foreground mb-4">Drag & drop or choose files to upload</p>
        <Button variant="soft" size="sm" :disabled="props.isAtLimit" @click="fileInputRef?.click()">
          Choose Files
        </Button>
      </template>
      <p class="text-xs text-muted-foreground mt-4">
        Supported: PDF, TXT, DOCX, PPTX, MD, JSON, HTML, XML, Audio (MP3, WAV, M4A, AAC, FLAC), Images, CSV
      </p>
      <p class="text-xs text-muted-foreground">Images: max 5MB each</p>
    </div>

    <Alert v-if="validationError" variant="destructive" class="mt-4">
      <PhWarning :size="16" />
      <AlertDescription>{{ validationError }}</AlertDescription>
    </Alert>
  </div>
</template>
