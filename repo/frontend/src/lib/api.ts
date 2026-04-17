/**
 * src/lib/api.ts
 * Axios instance configured for the local backend.
 * - Base URL from VITE_API_BASE_URL env var (local network only, no CDN)
 * - Attaches JWT access token from localStorage on every request
 * - On 401: attempts token refresh, then retries original request
 * - On network error: surfaces a clear offline message
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

// Empty string → relative URLs → requests go to the same origin as the page.
// In dev (Docker or local): Vite's /api proxy forwards them to Django.
// In production: nginx's /api location forwards them to gunicorn.
// Set VITE_API_BASE_URL only when you need to override (e.g. cross-origin staging).
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? ''

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

// ── Request interceptor — attach Bearer token ────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor — handle 401 / network errors ───────────────────
let isRefreshing = false
let pendingQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

function drainQueue(token: string | null, error: unknown) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (token) resolve(token)
    else reject(error)
  })
  pendingQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Network / timeout — backend unreachable
    if (!error.response) {
      return Promise.reject(
        new Error('Cannot reach the server. Check that the backend is running on your local network.'),
      )
    }

    // 401 — try refreshing the access token once
    if (error.response.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem('refresh_token')

      if (!refreshToken) {
        clearTokens()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve, reject })
        }).then((token) => {
          if (original.headers) original.headers['Authorization'] = `Bearer ${token}`
          return api(original)
        })
      }

      isRefreshing = true
      try {
        const { data } = await axios.post<{ access: string }>(
          `${BASE_URL}/api/auth/refresh/`,
          { refresh: refreshToken },
        )
        localStorage.setItem('access_token', data.access)
        drainQueue(data.access, null)
        if (original.headers) original.headers['Authorization'] = `Bearer ${data.access}`
        return api(original)
      } catch (refreshError) {
        drainQueue(null, refreshError)
        clearTokens()
        _unauthorizedCallback?.()   // notify AuthContext to clear user state
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  },
)

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access)
  localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function hasToken(): boolean {
  return !!localStorage.getItem('access_token')
}

// ── Unauthorized callback — set by AuthContext ────────────────────────────
// Called when a token refresh fails so React state can be cleared.
let _unauthorizedCallback: (() => void) | null = null
export function setUnauthorizedCallback(fn: () => void) {
  _unauthorizedCallback = fn
}
