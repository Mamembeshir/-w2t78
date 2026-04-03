/**
 * useNotifications.ts — React Query hooks for Notifications API (Phase 7).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

export type EventType =
  | 'SAFETY_STOCK_BREACH'
  | 'SAFETY_STOCK_RECOVERED'
  | 'CYCLE_COUNT_VARIANCE'
  | 'CRAWL_TASK_FAILED'
  | 'CANARY_ROLLBACK'
  | 'SLOW_MOVING_STOCK'
  | 'DIGEST'
  | 'SYSTEM'

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  SAFETY_STOCK_BREACH:    'Safety Stock Breach',
  SAFETY_STOCK_RECOVERED: 'Safety Stock Recovered',
  CYCLE_COUNT_VARIANCE:   'Cycle Count Variance',
  CRAWL_TASK_FAILED:      'Crawl Task Failed',
  CANARY_ROLLBACK:        'Canary Rollback',
  SLOW_MOVING_STOCK:      'Slow-Moving Stock',
  DIGEST:                 'Daily Digest',
  SYSTEM:                 'System',
}

export const ALL_EVENT_TYPES: EventType[] = Object.keys(EVENT_TYPE_LABELS) as EventType[]

export interface Notification {
  id: number
  event_type: EventType
  title: string
  body: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface Subscription {
  id: number
  event_type: EventType
  threshold_value: string | null
  is_active: boolean
  created_at: string
}

export interface DigestSchedule {
  id: number
  send_time: string
  last_sent_at: string | null
  updated_at: string
}

export interface OutboundMessage {
  id: number
  notification: number
  notification_title: string
  notification_event_type: string
  user_username: string
  channel: 'SMTP' | 'SMS'
  status: 'QUEUED' | 'SENT' | 'FAILED'
  queued_at: string
  sent_at: string | null
  error: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ── Unread count (for bell badge) ─────────────────────────────────────────────

export function useUnreadCount() {
  return useQuery<{ unread_count: number }>({
    queryKey: ['notifications-unread-count'],
    queryFn: () =>
      api.get<{ unread_count: number }>('/api/notifications/inbox/unread-count/').then(r => r.data),
    refetchInterval: 30_000,
  })
}

// ── Inbox ─────────────────────────────────────────────────────────────────────

export interface InboxFilters {
  unread?: boolean
  event_type?: string
  date_from?: string
}

export function useInbox(filters?: InboxFilters) {
  return useQuery<PaginatedResponse<Notification>>({
    queryKey: ['notifications-inbox', filters],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters?.unread) params.set('unread', '1')
      if (filters?.event_type) params.set('event_type', filters.event_type)
      if (filters?.date_from) params.set('date_from', filters.date_from)
      return api.get<PaginatedResponse<Notification>>(`/api/notifications/inbox/?${params}`).then(r => r.data)
    },
    refetchInterval: 30_000,
  })
}

export function useMarkRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      api.post<Notification>(`/api/notifications/inbox/${id}/read/`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications-inbox'] })
      qc.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api.post<{ marked_read: number }>('/api/notifications/inbox/read-all/').then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications-inbox'] })
      qc.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })
}

// ── Subscriptions ─────────────────────────────────────────────────────────────

export function useSubscriptions() {
  return useQuery<PaginatedResponse<Subscription>>({
    queryKey: ['notification-subscriptions'],
    queryFn: () =>
      api.get<PaginatedResponse<Subscription>>('/api/notifications/subscriptions/?page_size=100').then(r => r.data),
  })
}

export function useSubscribe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { event_type: EventType; threshold_value?: string }) =>
      api.post<Subscription>('/api/notifications/subscriptions/', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notification-subscriptions'] }),
  })
}

export function useUnsubscribe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      api.delete(`/api/notifications/subscriptions/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notification-subscriptions'] }),
  })
}

// ── Digest Schedule ───────────────────────────────────────────────────────────

export function useDigestSchedule() {
  return useQuery<DigestSchedule>({
    queryKey: ['notification-digest-schedule'],
    queryFn: () =>
      api.get<DigestSchedule>('/api/notifications/digest/').then(r => r.data),
  })
}

export function useUpdateDigestSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { send_time: string }) =>
      api.patch<DigestSchedule>('/api/notifications/digest/', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notification-digest-schedule'] }),
  })
}

// ── Outbound Queued (admin) ───────────────────────────────────────────────────

export function useOutboundQueued() {
  return useQuery<PaginatedResponse<OutboundMessage>>({
    queryKey: ['notification-outbound-queued'],
    queryFn: () =>
      api.get<PaginatedResponse<OutboundMessage>>('/api/notifications/outbound/queued/').then(r => r.data),
  })
}
