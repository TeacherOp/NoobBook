<script setup lang="ts">
/**
 * CreateProjectDialog Component
 * Educational Note: Controlled form with loading and error state.
 * - v-model replaces `value + onChange` on inputs
 * - emit('close') and emit('projectCreated', project) replace callback props
 * - @submit.prevent replaces `e.preventDefault()` in React's onSubmit
 */
import { ref, computed } from 'vue'
import { isAxiosError } from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { projectsAPI } from '@/lib/api'

interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  last_accessed: string
}

interface EditProject {
  id: string
  name: string
  description: string
}

const props = withDefaults(defineProps<{
  editProject?: EditProject | null
}>(), {
  editProject: null,
})

const emit = defineEmits<{
  close: []
  projectCreated: [project: Project]
}>()

const name = ref(props.editProject?.name ?? '')
const description = ref(props.editProject?.description ?? '')
const loading = ref(false)
const error = ref<string | null>(null)

const isEdit = computed(() => !!props.editProject)

async function handleSubmit() {
  if (!name.value.trim()) {
    error.value = 'Project name is required'
    return
  }

  loading.value = true
  error.value = null

  try {
    const response = isEdit.value
      ? await projectsAPI.update(props.editProject!.id, {
          name: name.value.trim(),
          description: description.value.trim(),
        })
      : await projectsAPI.create({
          name: name.value.trim(),
          description: description.value.trim(),
        })

    emit('projectCreated', response.data.project)
  } catch (err: unknown) {
    if (isAxiosError(err)) {
      error.value = err.response?.data?.error || 'Failed to save project'
    } else {
      error.value = 'Failed to save project'
    }
    loading.value = false
  }
}
</script>

<template>
  <Dialog open @update:open="(open) => { if (!open) emit('close') }">
    <DialogContent class="sm:max-w-md">
      <form @submit.prevent="handleSubmit">
        <DialogHeader>
          <DialogTitle>{{ isEdit ? 'Edit Project' : 'Create New Project' }}</DialogTitle>
          <DialogDescription>
            {{
              isEdit
                ? 'Update your project details'
                : 'Start a new project to organize your research and notes'
            }}
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 py-4">
          <div class="space-y-2">
            <Label for="name">Project Name *</Label>
            <Input
              id="name"
              v-model="name"
              placeholder="e.g., Q4 Research, Personal Notes"
              :disabled="loading"
              autofocus
            />
          </div>

          <div class="space-y-2">
            <Label for="description">Description (optional)</Label>
            <Input
              id="description"
              v-model="description"
              placeholder="Brief description of your project"
              :disabled="loading"
            />
          </div>

          <div v-if="error" class="text-sm text-destructive">{{ error }}</div>
        </div>

        <DialogFooter>
          <Button type="button" variant="soft" :disabled="loading" @click="emit('close')">
            Cancel
          </Button>
          <Button type="submit" :disabled="loading">
            {{
              loading
                ? (isEdit ? 'Updating...' : 'Creating...')
                : (isEdit ? 'Update Project' : 'Create Project')
            }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
