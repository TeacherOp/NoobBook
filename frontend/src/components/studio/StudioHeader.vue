<script setup lang="ts">
import { PhMagicWand } from '@phosphor-icons/vue'
</script>

<template>
  <div class="px-4 py-3 pl-12 border-b">
    <div class="flex items-center gap-2">
      <PhMagicWand :size="20" class="text-primary" />
      <h2 class="font-semibold">Studio</h2>
    </div>
    <p class="text-xs text-muted-foreground mt-1">Generate content from your sources</p>
  </div>
</template>
