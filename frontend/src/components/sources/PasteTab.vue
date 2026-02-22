<script setup lang="ts">
import { ref, computed } from 'vue'
import { PhClipboardText, PhCircleNotch } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const props = defineProps<{ isAtLimit: boolean }>()
const emit = defineEmits<{ addText: [content: string, name: string] }>()

const content = ref('')
const name = ref('')
const adding = ref(false)

const isValid = computed(() => content.value.trim() && name.value.trim())

async function handleAdd() {
  if (!isValid.value) return
  adding.value = true
  try {
    emit('addText', content.value.trim(), name.value.trim())
    content.value = ''
    name.value = ''
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div>
      <label class="text-sm font-medium mb-2 block">
        Source Name <span class="text-destructive">*</span>
      </label>
      <Input
        v-model="name"
        placeholder="e.g., Meeting Notes, Research Summary"
        :disabled="props.isAtLimit || adding"
      />
    </div>

    <div>
      <label class="text-sm font-medium mb-2 block">
        Content <span class="text-destructive">*</span>
      </label>
      <textarea
        v-model="content"
        class="w-full h-40 p-3 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
        placeholder="Paste your text content here..."
        :disabled="props.isAtLimit || adding"
      />
      <p class="text-xs text-muted-foreground mt-1">{{ content.length.toLocaleString() }} characters</p>
    </div>

    <Button class="w-full" :disabled="props.isAtLimit || adding || !isValid" @click="handleAdd">
      <PhCircleNotch v-if="adding" :size="16" class="mr-2 animate-spin" />
      <PhClipboardText v-else :size="16" class="mr-2" />
      {{ adding ? 'Adding...' : 'Add Pasted Content' }}
    </Button>
  </div>
</template>
