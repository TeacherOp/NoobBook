<script setup lang="ts">
/**
 * Dashboard Component
 * Educational Note: Main dashboard layout. Props replace React's prop interface.
 * v-if replaces conditional JSX. @click replaces onClick.
 */
import { ref } from 'vue'
import { PhGhost, PhGear, PhSignOut, PhWarning } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import ProjectList from '@/components/project/ProjectList.vue'
import AppSettings from './AppSettings.vue'

interface Props {
  refreshTrigger?: number
  isAdmin: boolean
  isAuthenticated: boolean
  onSignOut: () => Promise<void>
  userId: string
  userEmail: string | null
  userRole: string
}

const props = withDefaults(defineProps<Props>(), {
  refreshTrigger: 0,
})

const emit = defineEmits<{
  createNew: []
}>()

const appSettingsOpen = ref(false)
const signOutOpen = ref(false)
</script>

<template>
  <div class="min-h-screen bg-background">
    <!-- Header -->
    <header class="h-14 bg-background">
      <div class="container mx-auto px-4 h-full flex items-center justify-between">
        <div class="flex items-center gap-2">
          <PhGhost :size="24" weight="fill" class="text-primary" />
          <h1 class="text-lg font-semibold">NoobBook</h1>
        </div>

        <div class="flex items-center gap-2">
          <Button
            v-if="props.isAuthenticated"
            variant="soft"
            size="sm"
            class="gap-2"
            @click="signOutOpen = true"
          >
            <PhSignOut :size="16" />
            Sign out
          </Button>
          <Button
            v-if="props.isAuthenticated"
            variant="soft"
            size="sm"
            class="gap-2"
            @click="appSettingsOpen = true"
          >
            <PhGear :size="16" />
            {{ props.isAdmin ? 'Admin Settings' : 'Settings' }}
          </Button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-6 h-[calc(100vh-56px)] overflow-y-auto">
      <ProjectList
        :refresh-trigger="props.refreshTrigger"
        @create-new="emit('createNew')"
      />
    </main>

    <!-- Settings Dialog -->
    <AppSettings
      :open="appSettingsOpen"
      :user-id="props.userId"
      :user-email="props.userEmail"
      :user-role="props.userRole"
      :on-sign-out="props.onSignOut"
      @update:open="appSettingsOpen = $event"
    />

    <!-- Sign Out Confirmation -->
    <AlertDialog :open="signOutOpen" @update:open="signOutOpen = $event">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle class="flex items-center gap-2">
            <PhWarning :size="20" class="text-destructive" />
            Sign Out
          </AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to sign out? You'll need to log in again to access your projects.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button variant="soft" @click="signOutOpen = false">Cancel</Button>
          <Button
            variant="destructive"
            @click="() => { signOutOpen = false; props.onSignOut() }"
          >
            Sign Out
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
