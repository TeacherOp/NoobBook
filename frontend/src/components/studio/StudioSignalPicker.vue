<script setup lang="ts">
import { useStudioContext } from '@/composables/useStudio'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const { pickerOpen, selectedItem, selectedSignals, triggerGeneration, getItemTitle, getItemIcon } =
  useStudioContext()
</script>

<template>
  <Dialog :open="pickerOpen" @update:open="setPickerOpen($event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <component
            :is="selectedItem ? getItemIcon(selectedItem) : null"
            v-if="selectedItem && getItemIcon(selectedItem)"
            :size="20"
            class="text-primary"
          />
          Generate {{ selectedItem ? getItemTitle(selectedItem) : '' }}
        </DialogTitle>
        <DialogDescription>
          Multiple topics available. Choose which one to generate:
        </DialogDescription>
      </DialogHeader>

      <div class="flex flex-col gap-2 py-4 max-h-[50vh] overflow-y-auto">
        <Button
          v-for="signal in selectedSignals"
          :key="signal.id"
          variant="soft"
          class="h-auto p-3 justify-start text-left flex flex-col items-start gap-1 w-full min-w-0"
          @click="selectedItem && triggerGeneration(selectedItem, signal)"
        >
          <span class="font-medium text-sm line-clamp-2 w-full">{{ signal.direction }}</span>
          <span class="text-xs text-muted-foreground">
            {{ signal.sources.length }} source{{ signal.sources.length !== 1 ? 's' : '' }}
          </span>
        </Button>
      </div>
    </DialogContent>
  </Dialog>
</template>
