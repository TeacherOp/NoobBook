<script setup lang="ts">
import { ref, computed } from 'vue'
import { PhPlus, PhTrash, PhCircleNotch, PhInfo } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = defineProps<{ isAtLimit: boolean }>()
const emit = defineEmits<{ addResearch: [topic: string, description: string, links: string[]] }>()

const topic = ref('')
const description = ref('')
const links = ref<string[]>([])
const newLink = ref('')
const researching = ref(false)

const MIN_DESC = 50
const descValid = computed(() => description.value.trim().length >= MIN_DESC)
const isValid = computed(() => topic.value.trim() && descValid.value)

function ensureProtocol(url: string) {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`
}

function addLink() {
  if (!newLink.value.trim()) return
  links.value.push(ensureProtocol(newLink.value.trim()))
  newLink.value = ''
}

function removeLink(index: number) {
  links.value.splice(index, 1)
}

async function handleResearch() {
  if (!isValid.value) return
  researching.value = true
  try {
    emit('addResearch', topic.value.trim(), description.value.trim(), [...links.value])
    topic.value = ''
    description.value = ''
    links.value = []
  } finally {
    researching.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-start gap-2 p-3 bg-muted/50 rounded-md text-xs text-muted-foreground">
      <PhInfo :size="14" class="mt-0.5 shrink-0" />
      <span>Deep Research uses an AI agent to research a topic across the web and synthesize findings into a comprehensive source document.</span>
    </div>

    <div>
      <label class="text-sm font-medium mb-2 block">Topic <span class="text-destructive">*</span></label>
      <Input
        v-model="topic"
        placeholder="e.g., Climate change impact on agriculture"
        :disabled="props.isAtLimit || researching"
      />
    </div>

    <div>
      <label class="text-sm font-medium mb-2 block">Description / Focus Areas <span class="text-destructive">*</span></label>
      <textarea
        v-model="description"
        class="w-full h-28 p-3 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        placeholder="Describe what specific aspects to research, key questions to answer, or areas to focus on..."
        :disabled="props.isAtLimit || researching"
      />
      <p class="text-xs mt-1" :class="descValid ? 'text-muted-foreground' : 'text-destructive'">
        {{ description.trim().length }} / {{ MIN_DESC }} characters minimum
      </p>
    </div>

    <div>
      <label class="text-sm font-medium mb-2 block">Reference Links (optional)</label>
      <div class="flex gap-2 mb-2">
        <Input
          v-model="newLink"
          placeholder="https://example.com"
          :disabled="props.isAtLimit || researching"
          @keydown.enter="addLink"
        />
        <Button size="icon" variant="soft" :disabled="!newLink.trim()" @click="addLink">
          <PhPlus :size="16" />
        </Button>
      </div>
      <div v-if="links.length" class="space-y-1">
        <div v-for="(link, i) in links" :key="i" class="flex items-center gap-2 text-xs">
          <span class="flex-1 truncate text-muted-foreground">{{ link }}</span>
          <button class="text-destructive hover:opacity-70" @click="removeLink(i)">
            <PhTrash :size="14" />
          </button>
        </div>
      </div>
    </div>

    <Button class="w-full" :disabled="props.isAtLimit || researching || !isValid" @click="handleResearch">
      <PhCircleNotch v-if="researching" :size="16" class="mr-2 animate-spin" />
      {{ researching ? 'Starting Research...' : 'Start Deep Research' }}
    </Button>
  </div>
</template>
