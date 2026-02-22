<script setup lang="ts">
/**
 * ProjectHeader Component
 * Educational Note: Complex header with dialogs, cost tracking, and memory management.
 * - `watch(costsVersion, loadCosts)` replaces React's `useEffect([costsVersion])`
 * - `onMounted(loadCosts)` replaces `useEffect([], loadCosts)` for initial load
 * - `computed()` replaces `useMemo()` for derived state
 * - `toast.success/error` from vue-sonner replaces custom React useToast hook
 */
import { ref, computed, watch, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  PhArrowLeft,
  PhDotsThreeVertical,
  PhPlus,
  PhTrash,
  PhFolderOpen,
  PhGear,
  PhCircleNotch,
  PhCurrencyDollar,
  PhBrain,
  PhCaretDown,
  PhCaretRight,
  PhPencilSimple,
  PhSignOut,
} from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { chatsAPI } from '@/lib/api/chats'
import { projectsAPI } from '@/lib/api'
import type { CostTracking, MemoryData } from '@/lib/api'
import type { PromptConfig } from '@/lib/api/chats'
import { createLogger } from '@/lib/logger'

const log = createLogger('project-header')

interface Project {
  id: string
  name: string
  description?: string
}

const props = defineProps<{
  project: Project
  costsVersion?: number
  onSignOut?: () => Promise<void>
}>()

const emit = defineEmits<{
  back: []
  delete: []
  rename: [newName: string]
}>()

// Dialog open state
const deleteDialogOpen = ref(false)
const settingsDialogOpen = ref(false)
const renameDialogOpen = ref(false)
const memoryDialogOpen = ref(false)

// Rename state
const renameValue = ref(props.project.name)
const renaming = ref(false)

// Cost tracking
const costs = ref<CostTracking | null>(null)

// Memory state
const memory = ref<MemoryData | null>(null)
const loadingMemory = ref(false)
const editedUserMemory = ref('')
const editedProjectMemory = ref('')
const savingMemory = ref(false)

// Prompts state (view-only)
const allPrompts = ref<PromptConfig[]>([])
const loadingPrompts = ref(false)
const expandedPrompts = ref<Set<string>>(new Set())

const memoryIsDirty = computed(
  () =>
    editedUserMemory.value !== (memory.value?.user_memory || '') ||
    editedProjectMemory.value !== (memory.value?.project_memory || '')
)

async function loadCosts() {
  try {
    const response = await projectsAPI.getCosts(props.project.id)
    if (response.data.success) {
      costs.value = response.data.costs
    }
  } catch (err) {
    log.error({ err }, 'failed to load costs')
  }
}

onMounted(loadCosts)

watch(() => props.costsVersion, (v) => {
  if (v && v > 0) loadCosts()
})

async function loadMemory() {
  try {
    loadingMemory.value = true
    const response = await projectsAPI.getMemory(props.project.id)
    if (response.data.success) {
      const mem = response.data.memory
      memory.value = mem
      editedUserMemory.value = mem.user_memory || ''
      editedProjectMemory.value = mem.project_memory || ''
    }
  } catch (err) {
    log.error({ err }, 'failed to load memory')
    toast.error('Failed to load memory')
  } finally {
    loadingMemory.value = false
  }
}

function handleOpenMemory() {
  memoryDialogOpen.value = true
  loadMemory()
}

async function handleSaveMemory() {
  try {
    savingMemory.value = true
    const updates: { user_memory?: string; project_memory?: string } = {}
    if (editedUserMemory.value !== (memory.value?.user_memory || ''))
      updates.user_memory = editedUserMemory.value
    if (editedProjectMemory.value !== (memory.value?.project_memory || ''))
      updates.project_memory = editedProjectMemory.value

    await projectsAPI.updateMemory(props.project.id, updates)
    memory.value = {
      user_memory: editedUserMemory.value || null,
      project_memory: editedProjectMemory.value || null,
    }
    toast.success('Memory saved')
  } catch (err) {
    log.error({ err }, 'failed to save memory')
    toast.error('Failed to save memory')
  } finally {
    savingMemory.value = false
  }
}

async function loadAllPrompts() {
  try {
    loadingPrompts.value = true
    const prompts = await chatsAPI.getAllPrompts()
    allPrompts.value = prompts
  } catch (err) {
    log.error({ err }, 'failed to load prompts')
    toast.error('Failed to load prompts')
  } finally {
    loadingPrompts.value = false
  }
}

function togglePromptExpanded(promptName: string) {
  const next = new Set(expandedPrompts.value)
  if (next.has(promptName)) next.delete(promptName)
  else next.add(promptName)
  expandedPrompts.value = next
}

function handleOpenSettings() {
  settingsDialogOpen.value = true
  if (allPrompts.value.length === 0) loadAllPrompts()
}

function getPromptId(prompt: PromptConfig): string {
  return prompt.name || prompt.filename.replace('_prompt.json', '').replace('.json', '')
}

function formatPromptName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/prompt$/i, '')
    .trim()
    .split(' ')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function formatCost(cost: number): string {
  return cost < 0.01 ? '0.00' : cost.toFixed(2)
}

function formatCostWithSymbol(cost: number): string {
  return cost < 0.01 ? '$0.00' : `$${cost.toFixed(2)}`
}

function formatTokens(tokens: number): string {
  return tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}K` : tokens.toString()
}

async function handleRename() {
  const trimmed = renameValue.value.trim()
  if (!trimmed || trimmed === props.project.name) return
  try {
    renaming.value = true
    emit('rename', trimmed)
    renameDialogOpen.value = false
  } catch (err) {
    log.error({ err }, 'failed to rename project')
    toast.error('Failed to rename project')
  } finally {
    renaming.value = false
  }
}
</script>

<template>
  <div class="h-14 flex items-center justify-between px-4 bg-background">
    <!-- Left side -->
    <div class="flex items-center gap-3">
      <Button variant="soft" size="icon" class="h-8 w-8" @click="emit('back')">
        <PhArrowLeft :size="16" />
      </Button>

      <div class="flex items-center gap-2">
        <PhFolderOpen :size="20" class="text-muted-foreground" />
        <h1 class="text-lg font-semibold">{{ props.project.name }}</h1>
      </div>

      <!-- Cost display -->
      <TooltipProvider v-if="costs && costs.total_cost > 0">
        <Tooltip>
          <TooltipTrigger as-child>
            <div class="flex items-center gap-1.5 px-2 py-1 bg-muted/50 rounded-md cursor-default">
              <PhCurrencyDollar :size="14" class="text-muted-foreground" />
              <span class="text-sm text-muted-foreground font-medium">
                {{ formatCost(costs.total_cost) }}
              </span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom" class="p-3">
            <div class="space-y-2 text-xs">
              <p class="font-semibold text-sm mb-2">API Usage Breakdown</p>

              <div
                v-if="costs.by_model.sonnet.input_tokens > 0 || costs.by_model.sonnet.output_tokens > 0"
                class="space-y-1"
              >
                <p class="font-medium">Sonnet</p>
                <div class="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                  <span>Input:</span>
                  <span>{{ formatTokens(costs.by_model.sonnet.input_tokens) }} tokens</span>
                  <span>Output:</span>
                  <span>{{ formatTokens(costs.by_model.sonnet.output_tokens) }} tokens</span>
                  <span>Cost:</span>
                  <span class="font-medium text-foreground">{{ formatCostWithSymbol(costs.by_model.sonnet.cost) }}</span>
                </div>
              </div>

              <div
                v-if="costs.by_model.haiku.input_tokens > 0 || costs.by_model.haiku.output_tokens > 0"
                class="space-y-1"
              >
                <p class="font-medium">Haiku</p>
                <div class="grid grid-cols-2 gap-x-4 gap-y-0.5 text-muted-foreground">
                  <span>Input:</span>
                  <span>{{ formatTokens(costs.by_model.haiku.input_tokens) }} tokens</span>
                  <span>Output:</span>
                  <span>{{ formatTokens(costs.by_model.haiku.output_tokens) }} tokens</span>
                  <span>Cost:</span>
                  <span class="font-medium text-foreground">{{ formatCostWithSymbol(costs.by_model.haiku.cost) }}</span>
                </div>
              </div>

              <div class="border-t pt-2 mt-2">
                <div class="flex justify-between font-medium">
                  <span>Total:</span>
                  <span>{{ formatCostWithSymbol(costs.total_cost) }}</span>
                </div>
              </div>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>

    <!-- Right side - Actions -->
    <div class="flex items-center gap-2">
      <Button variant="soft" size="sm" class="gap-2" @click="handleOpenMemory">
        <PhBrain :size="16" />
        Memory
      </Button>

      <Button variant="soft" size="sm" class="gap-2" @click="handleOpenSettings">
        <PhGear :size="16" />
        Project Settings
      </Button>

      <Button variant="soft" size="sm" class="gap-2" @click="emit('back')">
        <PhPlus :size="16" />
        New Project
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <Button variant="soft" size="icon" class="h-8 w-8">
            <PhDotsThreeVertical :size="16" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem @click="() => { renameValue = props.project.name; renameDialogOpen = true }">
            <PhPencilSimple :size="16" class="mr-2" />
            Rename Project
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            class="text-destructive focus:text-destructive"
            @click="deleteDialogOpen = true"
          >
            <PhTrash :size="16" class="mr-2" />
            Delete Project
          </DropdownMenuItem>
          <template v-if="props.onSignOut">
            <DropdownMenuSeparator />
            <DropdownMenuItem @click="props.onSignOut">
              <PhSignOut :size="16" class="mr-2" />
              Sign out
            </DropdownMenuItem>
          </template>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>

    <!-- Delete Confirmation Dialog -->
    <Dialog :open="deleteDialogOpen" @update:open="deleteDialogOpen = $event">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Are you absolutely sure?</DialogTitle>
          <DialogDescription>
            This will permanently delete "{{ props.project.name }}" and all of its data.
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="soft" @click="deleteDialogOpen = false">Cancel</Button>
          <Button
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            @click="() => { emit('delete'); deleteDialogOpen = false }"
          >
            Delete Project
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Rename Dialog -->
    <Dialog
      :open="renameDialogOpen"
      @update:open="(open) => { if (!renaming) renameDialogOpen = open }"
    >
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Rename Project</DialogTitle>
          <DialogDescription>Enter a new name for this project.</DialogDescription>
        </DialogHeader>
        <div class="py-4">
          <Input
            v-model="renameValue"
            placeholder="Project name"
            :disabled="renaming"
            autofocus
            @keydown.enter="handleRename"
          />
        </div>
        <DialogFooter>
          <Button variant="soft" :disabled="renaming" @click="renameDialogOpen = false">
            Cancel
          </Button>
          <Button
            :disabled="renaming || !renameValue.trim() || renameValue.trim() === props.project.name"
            @click="handleRename"
          >
            {{ renaming ? 'Saving...' : 'Save' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Project Settings Dialog -->
    <Dialog :open="settingsDialogOpen" @update:open="settingsDialogOpen = $event">
      <DialogContent class="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Project Settings</DialogTitle>
          <DialogDescription>Configure settings for "{{ props.project.name }}"</DialogDescription>
        </DialogHeader>

        <div class="space-y-6 py-4">
          <div class="space-y-3">
            <div>
              <Label>All System Prompts</Label>
              <p class="text-xs text-muted-foreground mt-1">
                View all prompt configurations used by the application (read-only)
              </p>
            </div>

            <div v-if="loadingPrompts" class="flex items-center justify-center py-4">
              <PhCircleNotch :size="20" class="animate-spin text-muted-foreground" />
              <span class="ml-2 text-sm text-muted-foreground">Loading prompts...</span>
            </div>
            <p v-else-if="allPrompts.length === 0" class="text-sm text-muted-foreground italic py-4">
              No prompts found in the prompts folder.
            </p>
            <div v-else class="space-y-2">
              <Collapsible
                v-for="prompt in allPrompts"
                :key="prompt.filename"
                :open="expandedPrompts.has(getPromptId(prompt))"
                @update:open="() => togglePromptExpanded(getPromptId(prompt))"
              >
                <div class="border rounded-lg">
                  <CollapsibleTrigger as-child>
                    <button class="w-full p-3 hover:bg-muted/50 transition-colors text-left">
                      <div class="flex items-start justify-between gap-3">
                        <div class="flex items-start gap-3 min-w-0">
                          <div class="pt-0.5">
                            <PhCaretDown
                              v-if="expandedPrompts.has(getPromptId(prompt))"
                              :size="16"
                              class="text-muted-foreground"
                            />
                            <PhCaretRight v-else :size="16" class="text-muted-foreground" />
                          </div>
                          <div class="min-w-0">
                            <div class="font-medium">{{ formatPromptName(getPromptId(prompt)) }}</div>
                            <div class="text-xs text-muted-foreground">({{ prompt.filename }})</div>
                          </div>
                        </div>
                        <div class="flex items-center gap-3 text-xs text-muted-foreground shrink-0 pt-0.5">
                          <span v-if="prompt.model">{{ prompt.model }}</span>
                          <span v-if="prompt.temperature !== undefined">temp: {{ prompt.temperature }}</span>
                          <span v-if="prompt.max_tokens !== undefined">max: {{ prompt.max_tokens.toLocaleString() }}</span>
                        </div>
                      </div>
                    </button>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div class="border-t p-3 space-y-4 bg-muted/30">
                      <div v-if="prompt.description">
                        <Label class="text-xs">Description</Label>
                        <p class="text-sm text-muted-foreground mt-1">{{ prompt.description }}</p>
                      </div>
                      <div>
                        <Label class="text-xs">System Prompt</Label>
                        <div class="mt-1 p-2 bg-background rounded border max-h-48 overflow-y-auto">
                          <pre class="text-xs font-mono whitespace-pre-wrap">{{ prompt.system_prompt }}</pre>
                        </div>
                      </div>
                      <div v-if="prompt.user_message || prompt.user_message_template">
                        <Label class="text-xs">
                          {{ prompt.user_message_template ? 'User Message Template' : 'User Message' }}
                        </Label>
                        <div class="mt-1 p-2 bg-background rounded border max-h-32 overflow-y-auto">
                          <pre class="text-xs font-mono whitespace-pre-wrap">{{ prompt.user_message || prompt.user_message_template }}</pre>
                        </div>
                      </div>
                    </div>
                  </CollapsibleContent>
                </div>
              </Collapsible>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="soft" @click="settingsDialogOpen = false">Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Memory Dialog -->
    <Dialog
      :open="memoryDialogOpen"
      @update:open="(open) => { if (!savingMemory) memoryDialogOpen = open }"
    >
      <DialogContent class="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <PhBrain :size="20" />
            Memory
          </DialogTitle>
          <DialogDescription>
            Edit what the AI remembers about you and this project
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-6 py-4">
          <div v-if="loadingMemory" class="flex items-center justify-center py-8">
            <PhCircleNotch :size="24" class="animate-spin text-muted-foreground" />
            <span class="ml-2 text-sm text-muted-foreground">Loading memory...</span>
          </div>
          <template v-else>
            <!-- User Memory -->
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <Label>User Memory</Label>
                <button
                  v-if="editedUserMemory"
                  class="text-xs text-muted-foreground hover:text-foreground transition-colors border rounded px-2 py-0.5"
                  @click="editedUserMemory = ''"
                >
                  Clear
                </button>
              </div>
              <p class="text-xs text-muted-foreground">Persists across all your projects</p>
              <Textarea
                v-model="editedUserMemory"
                placeholder="The AI will remember important details about you as you chat, or you can add them here."
                class="min-h-[100px] resize-y"
                :disabled="savingMemory"
              />
            </div>

            <!-- Project Memory -->
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <Label>Project Memory</Label>
                <button
                  v-if="editedProjectMemory"
                  class="text-xs text-muted-foreground hover:text-foreground transition-colors border rounded px-2 py-0.5"
                  @click="editedProjectMemory = ''"
                >
                  Clear
                </button>
              </div>
              <p class="text-xs text-muted-foreground">Specific to "{{ props.project.name }}"</p>
              <Textarea
                v-model="editedProjectMemory"
                placeholder="The AI will remember project-specific details as you chat, or you can add them here."
                class="min-h-[100px] resize-y"
                :disabled="savingMemory"
              />
            </div>
          </template>
        </div>

        <DialogFooter>
          <Button variant="soft" :disabled="savingMemory" @click="memoryDialogOpen = false">
            Cancel
          </Button>
          <Button :disabled="savingMemory || !memoryIsDirty" @click="handleSaveMemory">
            {{ savingMemory ? 'Saving...' : 'Save' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
