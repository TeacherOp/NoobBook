<script setup lang="ts">
/**
 * AuthPage Component
 * Educational Note: Vue equivalent of React's AuthPage.tsx.
 * - `ref()` replaces `useState()`
 * - `async function` replaces `async () =>`
 * - vue-sonner's `toast` replaces the custom React useToast hook
 * - v-model on Input replaces `value + onChange` controlled input pattern
 */
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { authAPI } from '@/lib/api/auth'
import { createLogger } from '@/lib/logger'

const log = createLogger('auth-page')

const props = defineProps<{
  onAuthenticated: () => Promise<void>
}>()

const portal = ref<'admin' | 'user'>('user')
const mode = ref<'signin' | 'signup'>('signin')
const email = ref('')
const password = ref('')
const submitting = ref(false)

async function handleSubmit() {
  if (!email.value || !password.value) {
    toast.error('Email and password are required')
    return
  }

  submitting.value = true
  try {
    const result =
      mode.value === 'signin'
        ? await authAPI.signIn(email.value, password.value)
        : await authAPI.signUp(email.value, password.value)

    if (!result.success) {
      toast.error(result.error || 'Authentication failed')
      return
    }

    toast.success(mode.value === 'signin' ? 'Signed in' : 'Account created')
    await props.onAuthenticated()
  } catch (err) {
    log.error({ err }, 'authentication failed')
    toast.error('Authentication failed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-background flex items-center justify-center px-4">
    <Card class="w-full max-w-md">
      <CardHeader class="space-y-1">
        <CardTitle>{{ portal === 'admin' ? 'Admin Access' : 'User Access' }}</CardTitle>
        <CardDescription>
          {{
            portal === 'admin'
              ? 'Admin portal — use an email listed in NOOBBOOK_ADMIN_EMAILS.'
              : 'User portal — standard access to chat and studio.'
          }}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <!-- Portal toggle -->
        <div class="mb-6 flex gap-2">
          <Button
            :variant="portal === 'admin' ? 'default' : 'outline'"
            size="sm"
            class="flex-1"
            :disabled="submitting"
            @click="portal = 'admin'"
          >
            Admin
          </Button>
          <Button
            :variant="portal === 'user' ? 'default' : 'outline'"
            size="sm"
            class="flex-1"
            :disabled="submitting"
            @click="portal = 'user'"
          >
            User
          </Button>
        </div>

        <Tabs v-model="mode">
          <TabsList class="grid w-full grid-cols-2">
            <TabsTrigger value="signin">
              {{ portal === 'admin' ? 'Admin sign in' : 'Sign in' }}
            </TabsTrigger>
            <TabsTrigger value="signup">
              {{ portal === 'admin' ? 'Admin sign up' : 'Sign up' }}
            </TabsTrigger>
          </TabsList>

          <!-- Sign In -->
          <TabsContent value="signin" class="mt-6 space-y-4">
            <div class="space-y-2">
              <Label for="signin-email">Email</Label>
              <Input
                id="signin-email"
                v-model="email"
                type="email"
                placeholder="you@example.com"
                :disabled="submitting"
              />
            </div>
            <div class="space-y-2">
              <Label for="signin-password">Password</Label>
              <Input
                id="signin-password"
                v-model="password"
                type="password"
                placeholder="••••••••"
                :disabled="submitting"
              />
            </div>
            <Button class="w-full" :disabled="submitting" @click="handleSubmit">
              {{ submitting ? 'Signing in…' : portal === 'admin' ? 'Sign in as admin' : 'Sign in' }}
            </Button>
          </TabsContent>

          <!-- Sign Up -->
          <TabsContent value="signup" class="mt-6 space-y-4">
            <div class="space-y-2">
              <Label for="signup-email">Email</Label>
              <Input
                id="signup-email"
                v-model="email"
                type="email"
                placeholder="you@example.com"
                :disabled="submitting"
              />
            </div>
            <div class="space-y-2">
              <Label for="signup-password">Password</Label>
              <Input
                id="signup-password"
                v-model="password"
                type="password"
                placeholder="Create a password"
                :disabled="submitting"
              />
            </div>
            <Button class="w-full" :disabled="submitting" @click="handleSubmit">
              {{
                submitting
                  ? 'Creating account…'
                  : portal === 'admin'
                    ? 'Create admin account'
                    : 'Create account'
              }}
            </Button>
            <p v-if="portal === 'admin'" class="text-xs text-muted-foreground">
              Admin role is granted only if the email is in NOOBBOOK_ADMIN_EMAILS.
            </p>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  </div>
</template>
