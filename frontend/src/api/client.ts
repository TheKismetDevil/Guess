/** Axios instance with auth interceptor. */

import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { emitAuthEvent } from '@/utils/authEvents'
import { isTokenExpired } from '@/utils/jwt'

const GUEST_PATHS = ['/login', '/register', '/reset-password']
const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/reset-password']

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

function clearStoredAuthAndRedirect(): Promise<never> {
  localStorage.removeItem('auth')
  emitAuthEvent({ type: 'auth-cleared' })
  redirectToLoginWithExpiredSession()
  // Halt this request so callers don't render a generic error before navigation
  return new Promise(() => {})
}

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(currentRefreshToken: string): Promise<string> {
  if (refreshPromise) {
    return refreshPromise
  }

  refreshPromise = (async () => {
    const res = await axios.post<{ data: { access_token: string } }>('/api/v1/auth/refresh', {
      refresh_token: currentRefreshToken,
    })
    const newToken = res.data?.data?.access_token
    if (typeof newToken !== 'string' || !newToken.trim()) {
      throw new Error('刷新令牌响应缺少 access_token')
    }

    const latestStored = localStorage.getItem('auth')
    if (latestStored) {
      try {
        const latestAuth = JSON.parse(latestStored)
        latestAuth.accessToken = newToken
        localStorage.setItem('auth', JSON.stringify(latestAuth))
      } catch {
        // ignore parse errors
      }
    }
    emitAuthEvent({ type: 'token-refreshed', accessToken: newToken })
    return newToken
  })().finally(() => {
    refreshPromise = null
  })

  return refreshPromise
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
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (isAuthEndpoint(config.url)) {
    return config
  }

  const stored = localStorage.getItem('auth')
  if (!stored) {
    return config
  }

  let auth: { accessToken?: string; refreshToken?: string } | null = null
  try {
    auth = JSON.parse(stored)
  } catch {
    return config
  }

  if (!auth?.accessToken) {
    return config
  }

  if (!isGuestPath() && isTokenExpired(auth.accessToken, 5)) {
    if (!auth.refreshToken || isTokenExpired(auth.refreshToken)) {
      return clearStoredAuthAndRedirect()
    }
    try {
      const newToken = await refreshAccessToken(auth.refreshToken)
      config.headers.Authorization = `Bearer ${newToken}`
      return config
    } catch (refreshErr) {
      if (axios.isAxiosError(refreshErr) && !refreshErr.response) {
        return Promise.reject(refreshErr)
      }
      return clearStoredAuthAndRedirect()
    }
  }

  config.headers.Authorization = `Bearer ${auth.accessToken}`
  return config
})

// Response interceptor: handle 401 with silent token refresh / redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401) {
      // Avoid loops on auth pages/endpoints and leave the error to the caller there
      if (isGuestPath() || isAuthEndpoint(originalRequest?.url)) {
        return Promise.reject(error)
      }

      // Try silent refresh once if we have a refresh token
      if (originalRequest && !originalRequest._retry) {
        originalRequest._retry = true
        const stored = localStorage.getItem('auth')
        if (stored) {
          let auth: { accessToken?: string; refreshToken?: string } | null = null
          try {
            auth = JSON.parse(stored)
          } catch {
            auth = null
          }

          // Reuse an already-refreshed token if a parallel request just updated localStorage
          if (
            auth?.accessToken &&
            !isTokenExpired(auth.accessToken, 5) &&
            originalRequest.headers?.Authorization &&
            originalRequest.headers.Authorization !== `Bearer ${auth.accessToken}`
          ) {
            originalRequest.headers.Authorization = `Bearer ${auth.accessToken}`
            return apiClient(originalRequest)
          }

          if (auth?.refreshToken && !isTokenExpired(auth.refreshToken)) {
            try {
              const newToken = await refreshAccessToken(auth.refreshToken)
              originalRequest.headers.Authorization = `Bearer ${newToken}`
              return apiClient(originalRequest)
            } catch (refreshErr) {
              if (axios.isAxiosError(refreshErr) && !refreshErr.response) {
                return Promise.reject(refreshErr)
              }
              return clearStoredAuthAndRedirect()
            }
          }
        }
      }

      // No refresh token, refresh failed, or retry also failed: force login
      return clearStoredAuthAndRedirect()
    }

    return Promise.reject(error)
  },
)

export default apiClient
