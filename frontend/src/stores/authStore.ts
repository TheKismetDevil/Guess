import { defineStore } from 'pinia'
import { ref, computed, onScopeDispose } from 'vue'
import { register as registerApi, login as loginApi } from '@/api/auth'
import { subscribeAuthEvents } from '@/utils/authEvents'
import { getTokenExpiry } from '@/utils/jwt'
import type { LoginRequest, RegisterRequest, UserInfo } from '@/types/auth'

const GUEST_PATHS = ['/login', '/register', '/reset-password']
const MAX_TIMEOUT_MS = 2_147_483_647

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  let sessionExpiryTimer: ReturnType<typeof setTimeout> | null = null
  let hasPersistedSession = false

  function setUser(u: UserInfo | null) {
    user.value = u
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
  }

  function clearSessionExpiryTimer() {
    if (sessionExpiryTimer) {
      clearTimeout(sessionExpiryTimer)
      sessionExpiryTimer = null
    }
  }

  function redirectToLoginWithExpiredSession() {
    if (typeof window === 'undefined') return
    const pathname = window.location.pathname
    if (GUEST_PATHS.includes(pathname)) {
      return
    }
    const currentPath = window.location.pathname + window.location.search
    window.location.href = `/login?session=expired&redirect=${encodeURIComponent(currentPath)}`
  }

  function clearMemoryState() {
    hasPersistedSession = false
    clearSessionExpiryTimer()
    user.value = null
    accessToken.value = null
    refreshToken.value = null
  }

  function clearAuth() {
    clearMemoryState()
    localStorage.removeItem('auth')
  }

  function handleSessionExpired() {
    const wasAdmin = user.value?.is_admin ?? false
    clearAuth()
    if (wasAdmin) {
      redirectToLoginWithExpiredSession()
    }
  }

  function scheduleSessionExpiry(token: string) {
    clearSessionExpiryTimer()
    if (!user.value) {
      return
    }
    const exp = getTokenExpiry(token)
    if (!exp) return

    const delay = exp * 1000 - Date.now()
    if (delay <= 0) {
      handleSessionExpired()
      return
    }

    sessionExpiryTimer = setTimeout(restoreSession, Math.min(delay, MAX_TIMEOUT_MS))
  }

  function persistAuth(data: { accessToken: string; refreshToken: string; user: UserInfo }) {
    hasPersistedSession = true
    setUser(data.user)
    setTokens(data.accessToken, data.refreshToken)
    const sessionId = Array.from(crypto.getRandomValues(new Uint32Array(4))).join('-')
    localStorage.setItem('auth', JSON.stringify({ ...data, sessionId }))
    scheduleSessionExpiry(data.refreshToken)
  }

  async function register(data: RegisterRequest) {
    const result = await registerApi(data)
    persistAuth({
      accessToken: result.access_token,
      refreshToken: result.refresh_token,
      user: result.user,
    })
  }

  async function login(data: LoginRequest) {
    const result = await loginApi(data)
    persistAuth({
      accessToken: result.access_token,
      refreshToken: result.refresh_token,
      user: result.user,
    })
  }

  function logout() {
    clearAuth()
  }

  // Restore / sync session from localStorage
  function restoreSession() {
    const stored = localStorage.getItem('auth')
    if (!stored) {
      if (hasPersistedSession) {
        const wasOnAdminRoute =
          typeof window !== 'undefined' && window.location.pathname.startsWith('/admin')
        clearMemoryState()
        if (wasOnAdminRoute) {
          window.location.href = '/'
        }
      }
      return
    }

    try {
      const parsed = JSON.parse(stored)
      if (!parsed?.user || !parsed?.refreshToken) {
        localStorage.removeItem('auth')
        if (hasPersistedSession) {
          clearMemoryState()
        }
        return
      }
      hasPersistedSession = true
      setUser(parsed.user)
      setTokens(parsed.accessToken ?? '', parsed.refreshToken)
      scheduleSessionExpiry(parsed.refreshToken)
    } catch {
      localStorage.removeItem('auth')
      if (hasPersistedSession) {
        clearMemoryState()
      }
    }
  }

  const unsubscribeAuthEvents = subscribeAuthEvents((event) => {
    if (event.type === 'token-refreshed') {
      restoreSession()
    } else if (event.type === 'auth-cleared') {
      clearMemoryState()
    }
  })

  function handleVisibilityChange() {
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      restoreSession()
    }
  }

  function handleWindowFocus() {
    restoreSession()
  }

  function handleStorageEvent(event: StorageEvent) {
    if (event.key === 'auth' || event.key === null) {
      if (!event.newValue && user.value) {
        hasPersistedSession = true
      }
      restoreSession()
    }
  }

  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('focus', handleWindowFocus)
    window.addEventListener('storage', handleStorageEvent)
  }
  if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }

  onScopeDispose(() => {
    clearSessionExpiryTimer()
    unsubscribeAuthEvents()
    if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
      window.removeEventListener('focus', handleWindowFocus)
      window.removeEventListener('storage', handleStorageEvent)
    }
    if (typeof document !== 'undefined' && typeof document.removeEventListener === 'function') {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  })

  return {
    user,
    accessToken,
    refreshToken,
    isLoggedIn,
    isAdmin,
    setUser,
    setTokens,
    persistAuth,
    clearAuth,
    register,
    login,
    logout,
    restoreSession,
  }
})
