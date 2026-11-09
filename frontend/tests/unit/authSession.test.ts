import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { emitAuthEvent } from '@/utils/authEvents'

function makeJwt(expSeconds: number): string {
  const encode = (obj: Record<string, unknown>) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: 'admin', exp: expSeconds })}.sig`
}

describe('useAuthStore session expiry and cross-context sync', () => {
  const originalLocation = window.location

  beforeEach(() => {
    localStorage.clear()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        pathname: '/races/1',
        search: '',
        href: 'http://localhost:5173/races/1',
      },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    })
  })

  it('keeps accessToken and admin state in sync with apiClient auth events', () => {
    const scope = effectScope()
    scope.run(() => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const authStore = useAuthStore()
      const nowSec = Math.floor(Date.now() / 1000)

      authStore.persistAuth({
        accessToken: makeJwt(nowSec + 60),
        refreshToken: makeJwt(nowSec + 3600),
        user: { id: 1, username: 'admin', qq: '10001', is_admin: true },
      })

      expect(authStore.isAdmin).toBe(true)
      expect(authStore.isLoggedIn).toBe(true)

      const renewed = makeJwt(nowSec + 1800)
      emitAuthEvent({ type: 'token-refreshed', accessToken: renewed })
      expect(authStore.accessToken).toBe(renewed)
      expect(authStore.isAdmin).toBe(true)

      emitAuthEvent({ type: 'auth-cleared' })
      expect(authStore.isAdmin).toBe(false)
      expect(authStore.isLoggedIn).toBe(false)
      expect(authStore.user).toBeNull()
    })
    scope.stop()
  })

  it('clears admin state and redirects on visibility/focus wakeup if refreshToken expired during sleep', () => {
    const scope = effectScope()
    scope.run(() => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const authStore = useAuthStore()

      const baseMs = Date.now()
      const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(baseMs)
      const baseSec = Math.floor(baseMs / 1000)

      authStore.persistAuth({
        accessToken: makeJwt(baseSec + 1800),
        refreshToken: makeJwt(baseSec + 3600),
        user: { id: 1, username: 'admin', qq: '10001', is_admin: true },
      })
      expect(authStore.isAdmin).toBe(true)

      // Simulate system sleep advancing wall-clock past refreshToken exp without firing setTimeout
      nowSpy.mockReturnValue(baseMs + 7200 * 1000)
      window.dispatchEvent(new Event('focus'))

      expect(authStore.isAdmin).toBe(false)
      expect(authStore.isLoggedIn).toBe(false)
      expect(localStorage.getItem('auth')).toBeNull()
      expect(window.location.href).toBe('/login?session=expired&redirect=%2Fraces%2F1')
    })
    scope.stop()
  })

  it('clears admin state when another tab logs out via storage event', () => {
    const scope = effectScope()
    scope.run(() => {
      window.location.pathname = '/admin/horses'
      const pinia = createPinia()
      setActivePinia(pinia)
      const authStore = useAuthStore()
      const nowSec = Math.floor(Date.now() / 1000)

      authStore.persistAuth({
        accessToken: makeJwt(nowSec + 1800),
        refreshToken: makeJwt(nowSec + 3600),
        user: { id: 1, username: 'admin', qq: '10001', is_admin: true },
      })
      expect(authStore.isAdmin).toBe(true)

      // Simulate another tab clearing localStorage
      localStorage.removeItem('auth')
      window.dispatchEvent(new StorageEvent('storage', { key: 'auth', newValue: null }))

      expect(authStore.isAdmin).toBe(false)
      expect(authStore.isLoggedIn).toBe(false)
      expect(window.location.href).toBe('/')
    })
    scope.stop()
  })
})
