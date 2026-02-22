/**
 * Auth Composable
 *
 * Educational Note: Vue's provide/inject is the equivalent of React Context.
 * The useAuthProvider() is called once at the app root (App.vue) to create
 * shared auth state. Child components call useAuth() to access it via inject().
 *
 * Auth Flow:
 * 1. On mount, check for existing tokens in localStorage
 * 2. If token exists, validate by calling GET /auth/me
 * 3. If valid → set user. If expired → clear tokens.
 * 4. Login/signup store new tokens and set user state
 * 5. Logout clears tokens and resets user state
 */

import { ref, type InjectionKey, provide, inject, onMounted } from 'vue'
import { authAPI } from '@/lib/api/auth'
import { clearSession } from '@/lib/auth/session'
import { createLogger } from '@/lib/logger'

const log = createLogger('auth')

// ==================== Types ====================

export interface AuthUser {
  id: string
  email: string | null
  role: 'admin' | 'user'
}

export interface AuthContext {
  user: ReturnType<typeof ref<AuthUser | null>>
  loading: ReturnType<typeof ref<boolean>>
  isAuthenticated: ReturnType<typeof ref<boolean>>
  isAdmin: ReturnType<typeof ref<boolean>>
  authRequired: ReturnType<typeof ref<boolean>>
  authReady: ReturnType<typeof ref<boolean>>
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string; role?: 'admin' | 'user' }>
  signup: (email: string, password: string) => Promise<{ success: boolean; error?: string; role?: 'admin' | 'user' }>
  logout: () => Promise<void>
  refreshAuth: () => Promise<void>
}

// ==================== Injection Key ====================

const AUTH_KEY: InjectionKey<AuthContext> = Symbol('auth')

// ==================== Provider (called in App.vue) ====================

/**
 * Creates auth state and provides it to the component tree.
 * Call this once in App.vue's setup.
 */
export function useAuthProvider(): AuthContext {
  const user = ref<AuthUser | null>(null)
  const loading = ref(true)
  const isAuthenticated = ref(false)
  const isAdmin = ref(false)
  const authRequired = ref(false)
  const authReady = ref(false)

  const refreshAuth = async () => {
    try {
      const res = await authAPI.me()
      authRequired.value = Boolean(res?.auth_required)
      isAuthenticated.value = Boolean(res?.user?.is_authenticated)
      isAdmin.value = Boolean(res?.user?.is_admin)

      if (res?.user?.is_authenticated) {
        user.value = {
          id: res.user.id || '',
          email: res.user.email || null,
          role: res.user.role === 'admin' ? 'admin' : 'user',
        }
      } else {
        user.value = null
      }
    } catch (err) {
      log.error({ err }, 'auth check failed')
      authRequired.value = false
      isAuthenticated.value = false
      isAdmin.value = false
      user.value = null
    } finally {
      authReady.value = true
      loading.value = false
    }
  }

  const login = async (email: string, password: string) => {
    try {
      const result = await authAPI.signIn(email, password)

      if (result.success && result.user) {
        const meResponse = await authAPI.me()
        const role: 'admin' | 'user' = meResponse.user?.role === 'admin' ? 'admin' : 'user'
        user.value = { id: result.user.id, email: result.user.email || null, role }
        isAuthenticated.value = true
        isAdmin.value = role === 'admin'
        return { success: true as const, role }
      }

      return { success: false as const, error: result.error || 'Login failed' }
    } catch (err: any) {
      const message = err.response?.data?.error || 'Login failed. Please try again.'
      return { success: false as const, error: message }
    }
  }

  const signup = async (email: string, password: string) => {
    try {
      const result = await authAPI.signUp(email, password)

      if (result.success && result.user) {
        const meResponse = await authAPI.me()
        const role: 'admin' | 'user' = meResponse.user?.role === 'admin' ? 'admin' : 'user'
        user.value = { id: result.user.id, email: result.user.email || null, role }
        isAuthenticated.value = true
        isAdmin.value = role === 'admin'
        return { success: true as const, role }
      }

      return { success: false as const, error: result.error || 'Signup failed' }
    } catch (err: any) {
      const message = err.response?.data?.error || 'Signup failed. Please try again.'
      return { success: false as const, error: message }
    }
  }

  const logout = async () => {
    try {
      await authAPI.signOut()
    } catch {
      // Proceed with local logout even if server call fails
    }
    clearSession()
    user.value = null
    isAuthenticated.value = false
    isAdmin.value = false
  }

  // Check existing session on mount
  onMounted(() => {
    refreshAuth()
  })

  const auth: AuthContext = {
    user,
    loading,
    isAuthenticated,
    isAdmin,
    authRequired,
    authReady,
    login,
    signup,
    logout,
    refreshAuth,
  }

  provide(AUTH_KEY, auth)
  return auth
}

// ==================== Consumer Hook ====================

/**
 * Access auth state from any descendant component.
 * Must be used within a component where useAuthProvider() was called in an ancestor.
 */
export function useAuth(): AuthContext {
  const auth = inject(AUTH_KEY)
  if (!auth) {
    throw new Error('useAuth() must be used within a component where useAuthProvider() was called')
  }
  return auth
}
