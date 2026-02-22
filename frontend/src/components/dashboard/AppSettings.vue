<script setup lang="ts">
/**
 * AppSettings Component
 * Educational Note: Admin Settings dialog with sidebar navigation.
 * Settings sections (Profile, Team, API Keys, etc.) will be implemented in Phase 4.7.
 * For now this is a functional stub that opens/closes correctly.
 */
import { ref, computed } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

type SettingsSection = 'profile' | 'team' | 'api-keys' | 'integrations' | 'design' | 'system'

const props = withDefaults(defineProps<{
  open: boolean
  userEmail?: string | null
  userRole?: string
  userId?: string
  onSignOut?: () => Promise<void>
}>(), {
  userEmail: null,
  userRole: 'user',
  userId: '',
  onSignOut: undefined,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const isAdmin = computed(() => props.userRole === 'admin')
const activeSection = ref<SettingsSection>('profile')

const allSections: { key: SettingsSection; label: string; adminOnly?: boolean }[] = [
  { key: 'profile', label: 'Profile' },
  { key: 'integrations', label: 'Integrations' },
  { key: 'team', label: 'Team', adminOnly: true },
  { key: 'api-keys', label: 'API Keys', adminOnly: true },
  { key: 'design', label: 'Design', adminOnly: true },
  { key: 'system', label: 'System', adminOnly: true },
]

const visibleSections = computed(() =>
  allSections.filter(s => !s.adminOnly || isAdmin.value)
)

function handleOpenChange(isOpen: boolean) {
  if (!isOpen) activeSection.value = 'profile'
  emit('update:open', isOpen)
}
</script>

<template>
  <Dialog :open="props.open" @update:open="handleOpenChange">
    <DialogContent class="max-w-6xl h-[85vh] p-0 gap-0 overflow-hidden bg-card flex flex-col">
      <!-- Header -->
      <DialogHeader class="flex-shrink-0 px-6 py-3 border-b">
        <DialogTitle>Settings</DialogTitle>
      </DialogHeader>

      <!-- Main content with sidebar -->
      <div class="flex flex-1 min-h-0">
        <!-- Sidebar -->
        <div class="w-56 border-r flex-shrink-0 flex flex-col gap-1 p-3">
          <button
            v-for="section in visibleSections"
            :key="section.key"
            class="w-full text-left px-3 py-2 rounded-md text-sm transition-colors"
            :class="activeSection === section.key
              ? 'bg-primary/10 text-primary font-medium'
              : 'hover:bg-muted text-muted-foreground hover:text-foreground'"
            @click="activeSection = section.key"
          >
            {{ section.label }}
          </button>
        </div>

        <!-- Content area (stubs — full implementation in Phase 4.7) -->
        <div class="flex-1 overflow-y-auto p-6 bg-white">
          <div class="text-sm text-muted-foreground italic">
            {{ activeSection }} section — coming in Phase 4.7
          </div>

          <!-- Profile section: show email + sign out for now -->
          <div v-if="activeSection === 'profile'" class="mt-4 space-y-4">
            <div v-if="props.userEmail" class="text-sm">
              <span class="font-medium">Email:</span> {{ props.userEmail }}
            </div>
            <div class="text-sm">
              <span class="font-medium">Role:</span> {{ props.userRole }}
            </div>
            <Button
              v-if="props.onSignOut"
              variant="destructive"
              size="sm"
              @click="props.onSignOut"
            >
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
