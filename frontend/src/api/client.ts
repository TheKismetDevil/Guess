/** Axios instance with auth interceptor. */

import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

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

// Request interceptor: attach auth token
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const stored = localStorage.getItem('auth')
  if (stored) {
    try {
      const auth = JSON.parse(stored)
      if (auth.accessToken) {
        config.headers.Authorization = `Bearer ${auth.accessToken}`
      }
    } catch {
      // ignore parse errors
    }
  }
  return config
})

// Response interceptor: handle 401 with token refresh / redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const guestPaths = ['/login', '/register', '/reset-password']

    function redirectToLoginWithExpiredSession() {
      if (guestPaths.includes(window.location.pathname)) {
        return
      }
      const currentPath = window.location.pathname + window.location.search
      window.location.href = `/login?session=expired&redirect=${encodeURIComponent(currentPath)}`
    }

    if (error.response?.status === 401) {
      // Avoid loops on auth pages and leave the error to the caller there
      if (guestPaths.includes(window.location.pathname)) {
        return Promise.reject(error)
      }

      // Try silent refresh once if we have a refresh token
      if (!originalRequest._retry) {
        originalRequest._retry = true
        const stored = localStorage.getItem('auth')
        if (stored) {
          try {
            const auth = JSON.parse(stored)
            if (auth.refreshToken) {
              try {
                const res = await axios.post<{ data: { access_token: string } }>('/api/v1/auth/refresh', {
                  refresh_token: auth.refreshToken,
                })
                const newToken = res.data?.data?.access_token
                if (typeof newToken !== 'string' || !newToken.trim()) {
                  throw new Error('刷新令牌响应缺少 access_token')
                }
                // Update localStorage
                auth.accessToken = newToken
                localStorage.setItem('auth', JSON.stringify(auth))
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                return apiClient(originalRequest)
              } catch {
                localStorage.removeItem('auth')
                redirectToLoginWithExpiredSession()
                // Halt this request so callers don't render a generic error before navigation
                return new Promise(() => {})
              }
            }
          } catch {
            // ignore parse errors
          }
        }
      }

      // No refresh token, refresh failed, or retry also failed: force login
      localStorage.removeItem('auth')
      redirectToLoginWithExpiredSession()
      return new Promise(() => {})
    }

    return Promise.reject(error)
  },
)

export default apiClient
