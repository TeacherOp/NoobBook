<script setup lang="ts">
/**
 * ProjectWorkspaceRoute
 * Educational Note: Equivalent to React's ProjectWorkspaceRoute function.
 * - `useRoute().params.projectId` replaces `useParams<{ projectId: string }>()`
 * - `useRouter().push('/')` replaces `navigate('/')`
 * - `onMounted` replaces the initial `useEffect`
 * - The auth composable provides logout for the sign-out dropdown
 */
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import ProjectWorkspace from './ProjectWorkspace.vue'
import { Toaster } from '@/components/ui/sonner'
import { projectsAPI } from '@/lib/api'
import { createLogger } from '@/lib/logger'

const log = createLogger('project-workspace-route')

interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  last_accessed: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const projectId = route.params.projectId as string
const project = ref<Project | null>(null)
const loading = ref(true)

onMounted(async () => {
  if (!projectId) {
    router.push('/')
    return
  }

  try {
    const response = await projectsAPI.get(projectId)
    project.value = response.data.project
  } catch (err) {
    log.error({ err }, 'failed to load project')
    router.push('/')
  } finally {
    loading.value = false
  }
})

async function handleDeleteProject(id: string) {
  try {
    await projectsAPI.delete(id)
    router.push('/')
  } catch (err) {
    log.error({ err }, 'failed to delete project')
  }
}

async function handleRenameProject(newName: string) {
  if (!project.value) return
  await projectsAPI.update(projectId, { name: newName })
  project.value = { ...project.value, name: newName }
}
</script>

<template>
  <!-- Global toast container -->
  <Toaster rich-colors />

  <!-- Loading spinner while fetching project -->
  <div v-if="loading" class="h-screen flex items-center justify-center bg-background">
    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
  </div>

  <ProjectWorkspace
    v-else-if="project"
    :project="project"
    :on-sign-out="auth.isAuthenticated.value ? auth.logout : undefined"
    @back="router.push('/')"
    @delete-project="handleDeleteProject"
    @rename-project="handleRenameProject"
  />
</template>
