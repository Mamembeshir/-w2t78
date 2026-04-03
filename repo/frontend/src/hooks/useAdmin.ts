/**
 * useAdmin.ts — React Query hooks for Admin API (users + audit log).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UserRecord {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: string
  is_active: boolean
  last_login: string | null
  date_joined: string
}

export interface AuditEntry {
  id: number
  user: string
  action: string
  model_name: string
  object_id: string
  changes: Record<string, unknown>
  ip_address: string | null
  timestamp: string
}

interface PagedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

interface CreateUserPayload {
  username: string
  password: string
  email?: string
  first_name?: string
  last_name?: string
  role: string
  is_active?: boolean
}

// ── Hooks ──────────────────────────────────────────────────────────────────────

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => api.get<PagedResponse<UserRecord>>('/api/users/').then(r => r.data),
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateUserPayload) =>
      api.post<UserRecord>('/api/users/', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<UserRecord> & { id: number }) =>
      api.patch<UserRecord>(`/api/users/${id}/`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useAuditLog(params?: { model?: string; action?: string; from_date?: string }) {
  return useQuery({
    queryKey: ['audit', params],
    queryFn: () =>
      api.get<PagedResponse<AuditEntry>>('/api/audit/', { params }).then(r => r.data),
  })
}
