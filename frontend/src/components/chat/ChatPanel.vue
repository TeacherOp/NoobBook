<script setup lang="ts">
/**
 * ChatPanel Component
 * Educational Note: Main orchestrator for the chat interface.
 * - `onMounted` + `watch` replace React's useEffect
 * - `useVoiceRecording` composable replaces the React hook
 * - `toast` from vue-sonner replaces the custom useToast hook
 */
import { ref, watch, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import { PhSparkle } from '@phosphor-icons/vue'
import { Skeleton } from '@/components/ui/skeleton'
import { chatsAPI, type Chat, type ChatMetadata } from '@/lib/api/chats'
import type { StudioSignal } from '@/lib/types/studio'
import { sourcesAPI, type Source } from '@/lib/api/sources'
import { useVoiceRecording } from '@/composables/useVoiceRecording'
import { exportChatAsMarkdown } from '@/lib/exportChatMarkdown'
import { createLogger } from '@/lib/logger'
import ChatHeader from './ChatHeader.vue'
import ChatMessages from './ChatMessages.vue'
import ChatInput from './ChatInput.vue'
import ChatList from './ChatList.vue'
import ChatEmptyState from './ChatEmptyState.vue'

const log = createLogger('chat-panel')

const props = defineProps<{
  projectId: string
  projectName: string
  sourcesVersion?: number
  selectedSourceIds: string[]
}>()

const emit = defineEmits<{
  costsChange: []
  signalsChange: [signals: StudioSignal[]]
  activeChatChange: [chatId: string | null, sourceIds: string[]]
}>()

// ── State ─────────────────────────────────────────────────────────────────────
const message = ref('')
const activeChat = ref<Chat | null>(null)
const showChatList = ref(false)
const allChats = ref<ChatMetadata[]>([])
const loading = ref(true)
const sending = ref(false)
const exportingChat = ref(false)
const sources = ref<Source[]>([])

const activeSources = () => props.selectedSourceIds.length

// ── Voice recording ───────────────────────────────────────────────────────────
const { isRecording, partialTranscript, transcriptionConfigured, startRecording, stopRecording } =
  useVoiceRecording({
    onError: (msg: string) => toast.error(msg),
    onTranscriptCommit: (text: string) => {
      const prev = message.value
      message.value = prev + (prev && !prev.endsWith(' ') ? ' ' : '') + text
    },
  })

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadSources() {
  try {
    sources.value = await sourcesAPI.listSources(props.projectId)
  } catch (err) {
    log.error({ err }, 'failed to load sources')
  }
}

async function loadFullChat(chatId: string) {
  try {
    const chat = await chatsAPI.getChat(props.projectId, chatId)
    activeChat.value = chat
    emit('activeChatChange', chat.id, chat.selected_source_ids ?? [])
  } catch (err) {
    log.error({ err }, 'failed to load chat')
    toast.error('Failed to load chat')
  }
}

async function loadChats() {
  try {
    loading.value = true
    const chats = await chatsAPI.listChats(props.projectId)
    allChats.value = chats
    if (chats.length > 0 && !activeChat.value) {
      await loadFullChat(chats[0].id)
    }
  } catch (err) {
    log.error({ err }, 'failed to load chats')
    toast.error('Failed to load chats')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadChats()
  loadSources()
})

watch(() => props.sourcesVersion, (v) => {
  if (v && v > 0) loadSources()
})

// Propagate studio signals to parent when activeChat changes
watch(activeChat, (chat) => {
  emit('signalsChange', chat?.studio_signals || [])
})

// ── Send message ──────────────────────────────────────────────────────────────
async function handleSend() {
  if (!message.value.trim() || !activeChat.value || sending.value) return

  const userMessage = message.value.trim()
  message.value = ''
  sending.value = true

  // Optimistic: add user message immediately
  const tempId = `temp-${Date.now()}`
  const tempMsg = { id: tempId, role: 'user' as const, content: userMessage, timestamp: new Date().toISOString() }
  activeChat.value = { ...activeChat.value, messages: [...activeChat.value.messages, tempMsg] }

  const chatId = activeChat.value.id

  try {
    const result = await chatsAPI.sendMessage(props.projectId, chatId, userMessage)

    // Replace temp message with real messages
    if (activeChat.value?.id === chatId) {
      activeChat.value = {
        ...activeChat.value,
        messages: [
          ...activeChat.value.messages.filter(m => m.id !== tempId),
          result.user_message,
          result.assistant_message,
        ],
        updated_at: new Date().toISOString(),
      }
    }

    await loadChats()
    emit('costsChange')

    // Quick fetch for signals (1s)
    setTimeout(async () => {
      try {
        const updated = await chatsAPI.getChat(props.projectId, chatId)
        if (activeChat.value?.id === chatId)
          activeChat.value = { ...activeChat.value, studio_signals: updated.studio_signals || [] }
      } catch { /* non-critical */ }
    }, 1000)

    // Delayed fetch for title (4s)
    setTimeout(async () => {
      try {
        const updated = await chatsAPI.getChat(props.projectId, chatId)
        if (activeChat.value?.id === chatId)
          activeChat.value = { ...activeChat.value, title: updated.title, studio_signals: updated.studio_signals || [] }
        allChats.value = allChats.value.map(c => c.id === chatId ? { ...c, title: updated.title } : c)
      } catch { /* non-critical */ }
    }, 4000)
  } catch (err) {
    log.error({ err }, 'failed to send message')
    toast.error('Failed to send message')
    if (activeChat.value)
      activeChat.value = { ...activeChat.value, messages: activeChat.value.messages.filter(m => m.id !== tempId) }
  } finally {
    sending.value = false
  }
}

// ── Chat management ───────────────────────────────────────────────────────────
async function handleNewChat() {
  try {
    const newChat = await chatsAPI.createChat(props.projectId, 'New Chat')
    await loadChats()
    await loadFullChat(newChat.id)
    showChatList.value = false
    toast.success('New chat created')
  } catch (err) {
    log.error({ err }, 'failed to create chat')
    toast.error('Failed to create chat')
  }
}

async function handleSelectChat(chatId: string) {
  await loadFullChat(chatId)
  showChatList.value = false
}

async function handleDeleteChat(chatId: string) {
  try {
    await chatsAPI.deleteChat(props.projectId, chatId)
    if (activeChat.value?.id === chatId) {
      activeChat.value = null
      emit('activeChatChange', null, [])
    }
    await loadChats()
    toast.success('Chat deleted')
  } catch (err) {
    log.error({ err }, 'failed to delete chat')
    toast.error('Failed to delete chat')
  }
}

async function handleRenameChat(chatId: string, newTitle: string) {
  try {
    await chatsAPI.updateChat(props.projectId, chatId, newTitle)
    await loadChats()
    if (activeChat.value?.id === chatId)
      activeChat.value = { ...activeChat.value, title: newTitle }
    toast.success('Chat renamed')
  } catch (err) {
    log.error({ err }, 'failed to rename chat')
    toast.error('Failed to rename chat')
  }
}

async function handleExportChat() {
  if (!activeChat.value) return
  exportingChat.value = true
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await exportChatAsMarkdown({ chat: activeChat.value as any, projectId: props.projectId, projectName: props.projectName })
    toast.success('Chat exported as Markdown')
  } catch (err) {
    log.error({ err }, 'failed to export chat')
    toast.error('Failed to export chat')
  } finally {
    exportingChat.value = false
  }
}

function handleMicClick() {
  if (isRecording.value) stopRecording()
  else startRecording()
}
</script>

<template>
  <!-- Loading skeleton -->
  <div v-if="loading" class="flex flex-col h-full bg-card">
    <div class="border-b px-4 py-3">
      <div class="flex items-center gap-2">
        <PhSparkle :size="20" class="text-primary" />
        <h2 class="font-semibold">Chat</h2>
      </div>
      <p class="text-xs text-muted-foreground mt-1">Ask questions about your sources or request analysis</p>
    </div>
    <div class="flex-1 p-6 space-y-4">
      <div class="flex justify-end"><Skeleton class="h-10 w-2/3 rounded-2xl" /></div>
      <div class="flex justify-start gap-3">
        <Skeleton class="h-8 w-8 rounded-full flex-shrink-0" />
        <div class="space-y-2 flex-1">
          <Skeleton class="h-4 w-full" />
          <Skeleton class="h-4 w-5/6" />
          <Skeleton class="h-4 w-3/4" />
        </div>
      </div>
      <div class="flex justify-end"><Skeleton class="h-8 w-1/2 rounded-2xl" /></div>
    </div>
  </div>

  <!-- Empty state -->
  <ChatEmptyState
    v-else-if="allChats.length === 0 && !activeChat"
    :project-name="props.projectName"
    @new-chat="handleNewChat"
  />

  <!-- Chat list -->
  <ChatList
    v-else-if="showChatList"
    :chats="allChats"
    @select-chat="handleSelectChat"
    @delete-chat="handleDeleteChat"
    @rename-chat="(id, title) => handleRenameChat(id, title)"
    @new-chat="handleNewChat"
  />

  <!-- Active chat -->
  <div v-else class="flex flex-col h-full min-h-0 min-w-0 w-full bg-card overflow-hidden">
    <ChatHeader
      :active-chat="activeChat"
      :all-chats="allChats"
      :active-sources="activeSources()"
      :total-sources="sources.length"
      :exporting-chat="exportingChat"
      @select-chat="handleSelectChat"
      @new-chat="handleNewChat"
      @show-chat-list="showChatList = true"
      @export-chat="handleExportChat"
    />

    <ChatMessages
      :messages="activeChat?.messages || []"
      :sending="sending"
      :project-id="props.projectId"
    />

    <ChatInput
      :message="message"
      :partial-transcript="partialTranscript"
      :is-recording="isRecording"
      :sending="sending"
      :transcription-configured="transcriptionConfigured"
      @update:message="message = $event"
      @send="handleSend"
      @mic-click="handleMicClick"
    />
  </div>
</template>
