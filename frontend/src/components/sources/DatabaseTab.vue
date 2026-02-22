<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { PhDatabase, PhArrowClockwise, PhCircleNotch } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api/client'
import { createLogger } from '@/lib/logger'

const log = createLogger('database-tab')

const props = defineProps<{ isAtLimit: boolean }>()
const emit = defineEmits<{
  addDatabase: [connectionId: string, name?: string, description?: string]
}>()

interface DbConnection { id: string; name: string; uri: string; type: string }

const connections = ref<DbConnection[]>([])
const loading = ref(false)
const selected = ref<string>('')
const displayName = ref('')
const description = ref('')
const adding = ref(false)

async function loadConnections() {
  loading.value = true
  try {
    const res = await api.get('/settings/database-connections')
    connections.value = res.data.connections || []
  } catch (err) {
    log.error({ err }, 'failed to load database connections')
  } finally {
    loading.value = false
  }
}

onMounted(loadConnections)

function maskUri(uri: string) {
  return uri.replace(/:\/\/([^:]+):([^@]+)@/, '://$1:***@')
}

async function handleAdd() {
  if (!selected.value) return
  adding.value = true
  try {
    emit('addDatabase', selected.value, displayName.value || undefined, description.value || undefined)
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <label class="text-sm font-medium">Database Connection</label>
      <Button variant="ghost" size="icon-sm" :disabled="loading" @click="loadConnections">
        <PhArrowClockwise :size="14" :class="loading ? 'animate-spin' : ''" />
      </Button>
    </div>

    <div v-if="loading" class="text-center py-4">
      <PhCircleNotch :size="20" class="animate-spin text-muted-foreground mx-auto" />
    </div>

    <div v-else-if="connections.length === 0" class="text-center py-4 text-sm text-muted-foreground">
      No database connections configured. Add one in Settings → API Keys.
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="conn in connections"
        :key="conn.id"
        class="flex items-center gap-3 p-3 border rounded-md cursor-pointer transition-colors"
        :class="selected === conn.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'"
        @click="selected = conn.id"
      >
        <PhDatabase :size="18" class="text-muted-foreground shrink-0" />
        <div class="flex-1 overflow-hidden">
          <p class="text-sm font-medium truncate">{{ conn.name }}</p>
          <p class="text-xs text-muted-foreground truncate">{{ maskUri(conn.uri) }}</p>
        </div>
      </div>
    </div>

    <div v-if="selected">
      <label class="text-sm font-medium mb-2 block">Display Name (optional)</label>
      <Input v-model="displayName" placeholder="e.g., Production DB" :disabled="adding" />
    </div>

    <div v-if="selected">
      <label class="text-sm font-medium mb-2 block">Description (optional)</label>
      <Input v-model="description" placeholder="Brief description of this database source" :disabled="adding" />
    </div>

    <Button
      class="w-full"
      :disabled="props.isAtLimit || adding || !selected"
      @click="handleAdd"
    >
      <PhCircleNotch v-if="adding" :size="16" class="mr-2 animate-spin" />
      {{ adding ? 'Adding...' : 'Add Database Source' }}
    </Button>
  </div>
</template>
