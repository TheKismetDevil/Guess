/** Axios instance with auth interceptor. */

import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { emitAuthEvent } from '@/utils/authEvents'
import { isTokenExpired } from '@/utils/jwt'

const GUEST_PATHS = ['/login', '/register', '/reset-password']
const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/reset-password']

type StoredAuth = {
  accessToken?: string
  refreshToken?: string
  sessionId?: string
}

interface SessionRequestConfig extends InternalAxiosRequestConfig {
  _authSession?: string | null
  _retry?: boolean
}

function readStoredAuth(): StoredAuth | null {
  try {
    return JSON.parse(localStorage.getItem('auth') ?? 'null')
  } catch {
    return null
  }
}

function sessionKey(auth: StoredAuth | null): string | null {
  // Sessions persisted before sessionId was introduced still have a stable refresh token.
  return auth?.sessionId ?? auth?.refreshToken ?? auth?.accessToken ?? null
}

function checkSession(expected: string | null, auth = readStoredAuth()): void {
  if (sessionKey(auth) !== expected) {
    throw new axios.CanceledError('登录会话已变更')
  }
}

function isGuestPath(): boolean {
  return typeof window !== 'undefined' && GUEST_PATHS.includes(window.location.pathname)
}

function isAuthEndpoint(url?: string): boolean {
  if (!url) return false
  return AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint))
}

function redirectToLoginWithExpiredSession(): void {
  if (typeof window === 'undefined' || isGuestPath()) {
    return
  }
  const currentPath = window.location.pathname + window.location.search
  window.location.href = `/login?session=expired&redirect=${encodeURIComponent(currentPath)}`
}

function clearStoredAuthAndRedirect(expected: string | null): Promise<never> {
  checkSession(expected)
  localStorage.removeItem('auth')
  emitAuthEvent({ type: 'auth-cleared' })
  redirectToLoginWithExpiredSession()
  // Halt this request so callers don't render a generic error before navigation
  return new Promise(() => {})
}

const refreshes = new Map<string, Promise<string>>()

async function refreshAccessToken(session: string, refreshToken: string): Promise<string> {
  const pending = refreshes.get(session)
  if (pending) {
    return pending
  }

  const refresh = (async () => {
    const res = await axios.post<{ data: { access_token: string } }>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    })
    const latestAuth = readStoredAuth()
    checkSession(session, latestAuth)

    const newToken = res.data?.data?.access_token
    if (typeof newToken !== 'string' || !newToken.trim()) {
      throw new Error('刷新令牌响应缺少 access_token')
    }

    localStorage.setItem('auth', JSON.stringify({ ...latestAuth, accessToken: newToken }))
    emitAuthEvent({ type: 'token-refreshed' })
    return newToken
  })().finally(() => {
    refreshes.delete(session)
  })

  refreshes.set(session, refresh)
  return refresh
}

function handleRefreshFailure(error: unknown, session: string): Promise<never> {
  checkSession(session)
  if (
    axios.isAxiosError(error) &&
    error.response?.status === 401 &&
    error.response.data?.detail?.code === 'INVALID_REFRESH_TOKEN'
  ) {
    return clearStoredAuthAndRedirect(session)
  }
  throw error
}

const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  paramsSerializer: (params) => {
    const parts: string[] = []
    for (const [key, value] of Object.entries(params)) {
      if (value == null) continue
      if (Array.isArray(value)) {
        value.forEach((v) => parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(v))}`))
      } else {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
      }
    }
    return parts.join('&')
  },
})

// Request interceptor: proactively refresh expired JWT access tokens & attach Bearer header
apiClient.interceptors.request.use(async (config: SessionRequestConfig) => {
  if (isAuthEndpoint(config.url)) {
    return config
  }

  const auth = readStoredAuth()
  if (config._authSession !== undefined) {
    checkSession(config._authSession, auth)
  }
  const session = sessionKey(auth)
  config._authSession = session

  if (!auth?.accessToken) {
    return config
  }

  if (session && !isGuestPath() && isTokenExpired(auth.accessToken, 5)) {
    if (!auth.refreshToken || isTokenExpired(auth.refreshToken)) {
      return clearStoredAuthAndRedirect(session)
    }
    try {
      const newToken = await refreshAccessToken(session, auth.refreshToken)
      checkSession(session)
      config.headers.Authorization = `Bearer ${newToken}`
      return config
    } catch (refreshErr) {
      return handleRefreshFailure(refreshErr, session)
    }
  }

  config.headers.Authorization = `Bearer ${auth.accessToken}`
  return config
})

// Response interceptor: handle 401 with silent token refresh / redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest: SessionRequestConfig | undefined = error.config

    if (error.response?.status === 401 && originalRequest?._authSession !== undefined) {
      // Avoid loops on auth pages/endpoints and leave the error to the caller there
      if (isGuestPath() || isAuthEndpoint(originalRequest?.url)) {
        return Promise.reject(error)
      }

      const session = originalRequest._authSession
      const auth = readStoredAuth()
      checkSession(session, auth)

      // Try silent refresh once if we have a refresh token
      if (!originalRequest._retry) {
        originalRequest._retry = true

        // The retry interceptor attaches the latest token for the same session.
        if (
          auth?.accessToken &&
          !isTokenExpired(auth.accessToken, 5) &&
          originalRequest.headers.Authorization &&
          originalRequest.headers.Authorization !== `Bearer ${auth.accessToken}`
        ) {
          return apiClient(originalRequest)
        }

        if (session && auth?.refreshToken && !isTokenExpired(auth.refreshToken)) {
          try {
            await refreshAccessToken(session, auth.refreshToken)
          } catch (refreshErr) {
            return handleRefreshFailure(refreshErr, session)
          }
          return apiClient(originalRequest)
        }
      }

      // No usable refresh token, or the retried request was also rejected.
      return clearStoredAuthAndRedirect(session)
    }

    return Promise.reject(error)
  },
)

export default apiClient
