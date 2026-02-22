<script setup lang="ts">
import { PhBooks, PhMagnifyingGlass, PhPlus } from '@phosphor-icons/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

defineProps<{
  searchQuery: string
  isAtLimit: boolean
}>()

const emit = defineEmits<{
  'update:searchQuery': [value: string]
  addClick: []
}>()
</script>

<template>
  <div>
    <!-- Header -->
    <div class="px-4 py-3 pr-12 border-b">
      <div class="flex items-center gap-2">
        <PhBooks :size="20" class="text-primary" />
        <h2 class="font-semibold">Sources</h2>
      </div>
      <p class="text-xs text-muted-foreground mt-1">All sources for your project</p>
    </div>

    <!-- Controls -->
    <div class="p-4 space-y-3">
      <div class="relative">
        <PhMagnifyingGlass :size="16" class="absolute left-2 top-2.5 text-muted-foreground" />
        <Input
          placeholder="Search sources..."
          :value="searchQuery"
          class="pl-8 h-9"
          @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <Button
        class="w-full gap-2"
        variant="soft"
        size="sm"
        :disabled="isAtLimit"
        @click="emit('addClick')"
      >
        <PhPlus :size="16" />
        Add sources
      </Button>
    </div>
  </div>
</template>
