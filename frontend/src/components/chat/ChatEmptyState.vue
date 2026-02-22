<script setup lang="ts">
import { PhSparkle, PhChatCircle, PhPlus } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'

defineProps<{ projectName: string }>()
const emit = defineEmits<{ newChat: [] }>()
</script>

<template>
  <div class="flex flex-col h-full bg-card">
    <div class="border-b px-4 py-3">
      <div class="flex items-center gap-2">
        <PhSparkle :size="20" class="text-primary" />
        <h2 class="font-semibold">Chat</h2>
      </div>
      <p class="text-xs text-muted-foreground mt-1">
        Ask questions about your sources or request analysis
      </p>
    </div>

    <div class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <PhChatCircle :size="48" class="mx-auto mb-4 text-muted-foreground" />
        <h3 class="text-lg font-semibold mb-2">No chats yet</h3>
        <p class="text-sm text-muted-foreground mb-4">
          Start a conversation to explore your project sources
        </p>
        <Button class="gap-2" @click="emit('newChat')">
          <PhPlus :size="16" />
          Start New Chat
        </Button>
      </div>
    </div>
  </div>
</template>
