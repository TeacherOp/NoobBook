<script setup lang="ts">
/**
 * DashboardRoute
 * Educational Note: This is the top-level route component for the dashboard.
 * It handles the auth-gate logic that React's App component handled inline.
 *
 * Pattern comparison:
 *   React: App.tsx — if (!authReady) show spinner; if (authRequired && !isAuthenticated) show AuthPage
 *   Vue:   DashboardRoute.vue — same guard, but living in the route component
 *          because App.vue is now a thin provide() shell + <router-view>
 *
 * useAuth() works because App.vue calls useAuthProvider() first, which provide()s
 * the auth context. This route component and all its children can inject it.
 */
import { ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import AuthPage from '@/components/auth/AuthPage.vue'
import Dashboard from './Dashboard.vue'
import CreateProjectDialog from './CreateProjectDialog.vue'
import { Toaster } from '@/components/ui/sonner'

const auth = useAuth()

// Dashboard-level state (mirrors React AppContent)
const showCreateDialog = ref(false)
const refreshTrigger = ref(0)

function handleProjectCreated() {
  showCreateDialog.value = false
  refreshTrigger.value++
}
</script>

<template>
  <!-- Global toast container (vue-sonner, positioned fixed) -->
  <Toaster rich-colors />

  <!-- Spinner while auth check is in flight -->
  <div v-if="!auth.authReady.value" class="h-screen flex items-center justify-center bg-background">
    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
  </div>

  <!-- Auth gate: show login page if auth is required but user is not logged in -->
  <AuthPage
    v-else-if="auth.authRequired.value && !auth.isAuthenticated.value"
    :on-authenticated="auth.refreshAuth"
  />

  <!-- Dashboard -->
  <template v-else>
    <Dashboard
      :refresh-trigger="refreshTrigger"
      :is-admin="auth.isAdmin.value ?? false"
      :is-authenticated="auth.isAuthenticated.value ?? false"
      :user-id="auth.user.value?.id ?? ''"
      :user-email="auth.user.value?.email ?? null"
      :user-role="auth.user.value?.role ?? 'user'"
      :on-sign-out="auth.logout"
      @create-new="showCreateDialog = true"
    />

    <CreateProjectDialog
      v-if="showCreateDialog"
      @close="showCreateDialog = false"
      @project-created="handleProjectCreated"
    />
  </template>
</template>
