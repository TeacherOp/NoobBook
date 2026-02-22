<script setup lang="ts">
import { useAuthProvider } from '@/composables/useAuth'

/**
 * App Root
 * Educational Note: useAuthProvider() is called once here to create shared auth
 * state via Vue's provide/inject system. All descendant components access this
 * state with useAuth() — the Vue equivalent of React Context.
 */
useAuthProvider()
</script>

<template>
  <router-view />
</template>
