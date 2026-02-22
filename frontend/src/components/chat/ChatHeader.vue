<script setup lang="ts">
import {
  PhSparkle, PhPlus, PhChatCircle, PhCaretDown, PhHash,
  PhBooks, PhDownloadSimple, PhCircleNotch,
} from '@phosphor-icons/vue'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import type { Chat, ChatMetadata } from '@/lib/api/chats'

const props = defineProps<{
  activeChat: Chat | null
  allChats: ChatMetadata[]
  activeSources: number
  totalSources: number
  exportingChat: boolean
}>()

const emit = defineEmits<{
  selectChat: [chatId: string]
  newChat: []
  showChatList: []
  exportChat: []
}>()

const hasMessages = () => (props.activeChat?.messages?.length ?? 0) > 0
</script>

<template>
  <div class="border-b px-4 py-3">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <PhSparkle :size="20" class="text-primary" />
        <DropdownMenu>
          <DropdownMenuTrigger class="flex items-center gap-1 hover:opacity-80 transition-opacity">
            <h2 class="font-semibold">{{ props.activeChat?.title || 'Chat' }}</h2>
            <PhCaretDown :size="14" class="text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" class="w-56">
            <DropdownMenuItem @click="emit('showChatList')">
              <PhChatCircle :size="16" class="mr-2" />
              View All Chats
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              v-for="chat in props.allChats.slice(0, 5)"
              :key="chat.id"
              :class="chat.id === props.activeChat?.id ? 'bg-accent' : ''"
              @click="emit('selectChat', chat.id)"
            >
              <PhHash :size="16" class="mr-2" />
              {{ chat.title }}
            </DropdownMenuItem>
            <template v-if="props.allChats.length > 5">
              <DropdownMenuSeparator />
              <DropdownMenuItem @click="emit('showChatList')">View more...</DropdownMenuItem>
            </template>
            <DropdownMenuSeparator />
            <DropdownMenuItem @click="emit('newChat')">
              <PhPlus :size="16" class="mr-2" />
              New Chat
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div class="flex items-center gap-2">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="sm"
                :disabled="!hasMessages() || props.exportingChat"
                class="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                @click="emit('exportChat')"
              >
                <PhCircleNotch v-if="props.exportingChat" :size="32" weight="bold" class="animate-spin" />
                <PhDownloadSimple v-else :size="32" weight="bold" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Export as Markdown</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <div class="flex items-center gap-1.5 px-2 py-1 bg-muted rounded-md">
          <PhBooks :size="16" class="text-primary" />
          <span class="text-sm font-medium">{{ props.activeSources }}/{{ props.totalSources }}</span>
        </div>
      </div>
    </div>
    <p class="text-xs text-muted-foreground mt-1">
      Ask questions about your sources or request analysis
    </p>
  </div>
</template>
