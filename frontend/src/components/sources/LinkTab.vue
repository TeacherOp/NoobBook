<script setup lang="ts">
import { ref } from 'vue'
import { PhPlus, PhYoutubeLogo, PhCircleNotch, PhGlobe } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = defineProps<{ isAtLimit: boolean }>()
const emit = defineEmits<{ addUrl: [url: string] }>()

const websiteUrl = ref('')
const youtubeUrl = ref('')
const addingWebsite = ref(false)
const addingYoutube = ref(false)

function ensureProtocol(url: string) {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`
}

async function handleAddWebsite() {
  if (!websiteUrl.value.trim()) return
  addingWebsite.value = true
  try {
    emit('addUrl', ensureProtocol(websiteUrl.value.trim()))
    websiteUrl.value = ''
  } finally {
    addingWebsite.value = false
  }
}

async function handleAddYoutube() {
  if (!youtubeUrl.value.trim()) return
  addingYoutube.value = true
  try {
    emit('addUrl', ensureProtocol(youtubeUrl.value.trim()))
    youtubeUrl.value = ''
  } finally {
    addingYoutube.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Website -->
    <div>
      <label class="text-sm font-medium mb-2 flex items-center gap-2">
        <PhGlobe :size="16" />
        Website URL
      </label>
      <div class="flex gap-2">
        <Input
          v-model="websiteUrl"
          placeholder="https://example.com"
          :disabled="props.isAtLimit || addingWebsite"
          @keydown.enter="handleAddWebsite"
        />
        <Button
          size="icon"
          variant="soft"
          :disabled="props.isAtLimit || addingWebsite || !websiteUrl.trim()"
          @click="handleAddWebsite"
        >
          <PhCircleNotch v-if="addingWebsite" :size="16" class="animate-spin" />
          <PhPlus v-else :size="16" />
        </Button>
      </div>
      <p class="text-xs text-muted-foreground mt-1">Add any website URL to use as a source</p>
    </div>

    <!-- YouTube -->
    <div>
      <label class="text-sm font-medium mb-2 flex items-center gap-2">
        <PhYoutubeLogo :size="16" />
        YouTube Video
      </label>
      <div class="flex gap-2">
        <Input
          v-model="youtubeUrl"
          placeholder="https://youtube.com/watch?v=..."
          :disabled="props.isAtLimit || addingYoutube"
          @keydown.enter="handleAddYoutube"
        />
        <Button
          size="icon"
          variant="soft"
          :disabled="props.isAtLimit || addingYoutube || !youtubeUrl.trim()"
          @click="handleAddYoutube"
        >
          <PhCircleNotch v-if="addingYoutube" :size="16" class="animate-spin" />
          <PhPlus v-else :size="16" />
        </Button>
      </div>
      <p class="text-xs text-muted-foreground mt-1">Add YouTube video URLs (transcript will be extracted)</p>
    </div>
  </div>
</template>
