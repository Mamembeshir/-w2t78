import { createContext, useEffect, useState, type ReactNode } from 'react'
import { api, clearTokens, hasToken, setTokens, setUnauthorizedCallback } from '@/lib/api'
import type { AuthContextType, LoginResponse, User } from '@/types'

export const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Register callback so api.ts can clear auth state when refresh fails
  useEffect(() => {
    setUnauthorizedCallback(() => setUser(null))
  }, [])

  // Restore session on mount
  useEffect(() => {
    if (!hasToken()) {
      setIsLoading(false)
      return
    }
    api
      .get<User>('/api/auth/me/')
      .then((res) => setUser(res.data))
      .catch(() => clearTokens())
      .finally(() => setIsLoading(false))
  }, [])

  async function login(username: string, password: string) {
    const res = await api.post<LoginResponse>('/api/auth/login/', { username, password })
    setTokens(res.data.access, res.data.refresh)
    setUser(res.data.user)
  }

  async function logout() {
    const refresh = localStorage.getItem('refresh_token')
    try {
      if (refresh) await api.post('/api/auth/logout/', { refresh })
    } catch {
      // best effort — clear local state regardless
    } finally {
      clearTokens()
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
