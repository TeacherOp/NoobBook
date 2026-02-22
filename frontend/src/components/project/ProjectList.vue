<script setup lang="ts">
/**
 * ProjectList Component
 * Educational Note: Data fetching with onMounted + watch pattern.
 * - `watch(refreshTrigger, loadProjects)` replaces `useEffect([refreshTrigger])`
 * - `onMounted(loadProjects)` replaces `useEffect([], loadProjects)` (initial fetch)
 */
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { PhPlus, PhTrash, PhClock, PhPencilSimple } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import CreateProjectDialog from '@/components/dashboard/CreateProjectDialog.vue'
import { projectsAPI } from '@/lib/api'
import { createLogger } from '@/lib/logger'

const log = createLogger('project-list')

interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  last_accessed: string
}

const props = withDefaults(defineProps<{
  refreshTrigger?: number
}>(), {
  refreshTrigger: 0,
})

const emit = defineEmits<{
  createNew: []
}>()

const router = useRouter()

const projects = ref<Project[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const deleteDialogOpen = ref(false)
const projectToDelete = ref<string | null>(null)
const editProject = ref<{ id: string; name: string; description: string } | null>(null)

async function loadProjects() {
  try {
    loading.value = true
    loadError.value = null
    const response = await projectsAPI.list()
    projects.value = response.data.projects || []
  } catch (err) {
    loadError.value = 'Failed to load projects'
    log.error({ err }, 'failed to load projects')
  } finally {
    loading.value = false
  }
}

onMounted(loadProjects)

// Re-fetch when parent increments refreshTrigger
watch(() => props.refreshTrigger, loadProjects)

async function handleOpenProject(project: Project) {
  try {
    await projectsAPI.open(project.id)
    router.push(`/projects/${project.id}`)
  } catch (err) {
    log.error({ err }, 'failed to open project')
  }
}

function handleDeleteClick(e: MouseEvent, projectId: string) {
  e.stopPropagation()
  projectToDelete.value = projectId
  deleteDialogOpen.value = true
}

async function handleConfirmDelete() {
  if (!projectToDelete.value) return
  try {
    await projectsAPI.delete(projectToDelete.value)
    await loadProjects()
  } catch (err) {
    log.error({ err }, 'failed to delete project')
  } finally {
    deleteDialogOpen.value = false
    projectToDelete.value = null
  }
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <!-- Loading -->
  <div v-if="loading" class="flex items-center justify-center h-screen">
    <div class="text-center">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
      <p class="mt-4 text-muted-foreground">Loading projects...</p>
    </div>
  </div>

  <!-- Error -->
  <div v-else-if="loadError" class="flex items-center justify-center h-screen">
    <div class="text-center">
      <p class="text-destructive mb-4">{{ loadError }}</p>
      <Button @click="loadProjects">Try Again</Button>
    </div>
  </div>

  <!-- Project grid -->
  <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    <!-- Create New Project Card -->
    <Card
      class="cursor-pointer bg-[#e8e7e4] hover:bg-[#dddcd8] border-transparent transition-colors"
      @click="emit('createNew')"
    >
      <CardContent class="flex flex-col items-center justify-center h-full min-h-[140px] py-8">
        <div class="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-3">
          <PhPlus :size="28" weight="bold" class="text-primary" />
        </div>
        <p class="font-semibold text-base">Create New Project</p>
      </CardContent>
    </Card>

    <!-- Existing Projects -->
    <Card
      v-for="project in projects"
      :key="project.id"
      class="cursor-pointer hover:bg-stone-50 transition-colors"
      @click="handleOpenProject(project)"
    >
      <CardHeader>
        <div class="flex justify-between items-start">
          <div class="flex-1">
            <CardTitle class="text-lg">{{ project.name }}</CardTitle>
            <CardDescription class="mt-1">
              {{ project.description || 'No description' }}
            </CardDescription>
          </div>
          <div class="flex items-center gap-1 ml-2">
            <Button
              variant="ghost"
              size="icon"
              @click.stop="editProject = { id: project.id, name: project.name, description: project.description }"
            >
              <PhPencilSimple :size="20" weight="bold" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              @click.stop="(e: MouseEvent) => handleDeleteClick(e, project.id)"
            >
              <PhTrash :size="20" weight="bold" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div class="flex items-center text-sm text-muted-foreground">
          <PhClock :size="16" weight="bold" class="mr-1" />
          Last opened: {{ formatDate(project.last_accessed) }}
        </div>
      </CardContent>
    </Card>
  </div>

  <!-- Delete Confirmation Dialog -->
  <Dialog :open="deleteDialogOpen" @update:open="deleteDialogOpen = $event">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Delete Project</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete this project? This action cannot be undone.
          All sources, chats, and data will be permanently deleted.
        </DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <Button variant="soft" @click="deleteDialogOpen = false">Cancel</Button>
        <Button variant="destructive" @click="handleConfirmDelete">Delete</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Edit Project Dialog -->
  <CreateProjectDialog
    v-if="editProject"
    :edit-project="editProject"
    @close="editProject = null"
    @project-created="() => { editProject = null; loadProjects() }"
  />
</template>
