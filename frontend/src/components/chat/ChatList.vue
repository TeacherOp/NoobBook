<script setup lang="ts">
import { ref, computed } from 'vue'
import { PhSparkle, PhPlus, PhClock, PhHash, PhTrash, PhPencilSimple, PhMagnifyingGlass, PhX } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import type { ChatMetadata } from '@/lib/api/chats'

const props = defineProps<{ chats: ChatMetadata[] }>()
const emit = defineEmits<{
  selectChat: [chatId: string]
  deleteChat: [chatId: string]
  renameChat: [chatId: string, newTitle: string]
  newChat: []
}>()

const searchQuery = ref('')
const renameDialogOpen = ref(false)
const renameChatId = ref<string | null>(null)
const renameValue = ref('')

const filteredChats = computed(() =>
  searchQuery.value
    ? props.chats.filter(c => c.title.toLowerCase().includes(searchQuery.value.toLowerCase()))
    : props.chats
)

function formatRelativeTime(timestamp: string): string {
  const diffMs = Date.now() - new Date(timestamp).getTime()
  const mins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMs / 3600000)
  const days = Math.floor(diffMs / 86400000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return new Date(timestamp).toLocaleDateString()
}

function openRename(chatId: string, currentTitle: string) {
  renameChatId.value = chatId
  renameValue.value = currentTitle
  renameDialogOpen.value = true
}

function submitRename() {
  if (renameChatId.value && renameValue.value.trim()) {
    emit('renameChat', renameChatId.value, renameValue.value.trim())
    renameDialogOpen.value = false
    renameChatId.value = null
    renameValue.value = ''
  }
}
</script>

<template>
  <div class="flex flex-col h-full bg-card">
    <div class="border-b px-4 py-3">
      <div class="flex items-center gap-2">
        <PhSparkle :size="20" class="text-primary" />
        <h2 class="font-semibold">All Chats</h2>
      </div>
      <p class="text-xs text-muted-foreground mt-1">Select a chat to continue or start a new one</p>
    </div>

    <div class="px-4 pt-4">
      <Button variant="soft" class="w-full gap-2" @click="emit('newChat')">
        <PhPlus :size="16" />
        New Chat
      </Button>
    </div>

    <div class="px-4 pt-3">
      <div class="relative">
        <PhMagnifyingGlass :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input v-model="searchQuery" placeholder="Search chats..." class="pl-9 pr-9" />
        <button
          v-if="searchQuery"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          @click="searchQuery = ''"
        >
          <PhX :size="14" />
        </button>
      </div>
      <p v-if="searchQuery" class="text-xs text-muted-foreground mt-2">
        Showing {{ filteredChats.length }} of {{ chats.length }} chats
      </p>
    </div>

    <ScrollArea class="flex-1">
      <div class="p-4 space-y-2">
        <div v-if="filteredChats.length === 0 && searchQuery" class="text-center py-8">
          <PhMagnifyingGlass :size="32" class="mx-auto text-muted-foreground mb-2" />
          <p class="text-sm text-muted-foreground">No chats found</p>
        </div>
        <div
          v-for="chat in filteredChats"
          :key="chat.id"
          class="p-3 border rounded-lg hover:bg-accent transition-colors group"
        >
          <div class="flex items-start justify-between mb-1">
            <div class="flex-1 cursor-pointer" @click="emit('selectChat', chat.id)">
              <div class="flex items-center gap-2">
                <PhHash :size="16" class="text-muted-foreground" />
                <h3 class="font-medium text-sm">{{ chat.title }}</h3>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-muted-foreground flex items-center gap-1">
                <PhClock :size="12" />
                {{ formatRelativeTime(chat.updated_at) }}
              </span>
              <Button
                variant="ghost"
                size="icon"
                class="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                @click.stop="openRename(chat.id, chat.title)"
              >
                <PhPencilSimple :size="14" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                class="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                @click.stop="emit('deleteChat', chat.id)"
              >
                <PhTrash :size="14" class="text-destructive" />
              </Button>
            </div>
          </div>
          <p
            class="text-xs text-muted-foreground line-clamp-2 cursor-pointer"
            @click="emit('selectChat', chat.id)"
          >
            {{ chat.message_count }} messages
          </p>
        </div>
      </div>
    </ScrollArea>
  </div>

  <!-- Rename Dialog -->
  <Dialog :open="renameDialogOpen" @update:open="renameDialogOpen = $event">
    <DialogContent class="sm:max-w-[400px]">
      <DialogHeader>
        <DialogTitle>Rename Chat</DialogTitle>
        <DialogDescription>Enter a new name for this chat.</DialogDescription>
      </DialogHeader>
      <div class="py-4">
        <Label for="chat-name" class="text-sm font-medium">Chat Name</Label>
        <Input
          id="chat-name"
          v-model="renameValue"
          placeholder="Enter chat name..."
          class="mt-2"
          @keydown.enter="submitRename"
        />
      </div>
      <DialogFooter>
        <Button variant="soft" @click="renameDialogOpen = false">Cancel</Button>
        <Button :disabled="!renameValue.trim()" @click="submitRename">Save</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
