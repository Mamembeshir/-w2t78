/**
 * InboxPage — Notification inbox (Phase 7.6).
 *
 * URL: /notifications
 *
 * Features:
 * - Paginated list of notifications (all, or filtered by unread/event_type/date)
 * - Click row to expand full body + mark as read
 * - "Mark all read" button
 * - Auto-refreshes every 30 seconds via React Query
 */
import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Select'
import {
  useInbox,
  useMarkRead,
  useMarkAllRead,
  ALL_EVENT_TYPES,
  EVENT_TYPE_LABELS,
  type Notification,
  type EventType,
} from '@/hooks/useNotifications'
import { useToast } from '@/hooks/useToast'

const EVENT_TYPE_VARIANT: Record<EventType, 'danger' | 'warning' | 'info' | 'neutral' | 'success'> = {
  SAFETY_STOCK_BREACH:    'danger',
  SAFETY_STOCK_RECOVERED: 'success',
  CYCLE_COUNT_VARIANCE:   'warning',
  CRAWL_TASK_FAILED:      'danger',
  CANARY_ROLLBACK:        'warning',
  SLOW_MOVING_STOCK:      'info',
  DIGEST:                 'neutral',
  SYSTEM:                 'neutral',
}

function NotificationRow({ n, onRead }: { n: Notification; onRead: (id: number) => void }) {
  const [expanded, setExpanded] = useState(false)

  function handleClick() {
    setExpanded(e => !e)
    if (!n.is_read) onRead(n.id)
  }

  return (
    <div
      className={`border border-surface-700 rounded-xl overflow-hidden cursor-pointer transition-colors ${
        n.is_read ? 'bg-surface-800/60' : 'bg-surface-800 border-l-2 border-l-primary-500'
      } hover:border-surface-600`}
      onClick={handleClick}
    >
      <div className="px-5 py-3 flex items-start gap-3">
        {/* Unread dot */}
        <div className="flex-shrink-0 mt-1.5">
          {!n.is_read ? (
            <span className="w-2 h-2 rounded-full bg-primary-400 block" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-transparent block" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <Badge variant={EVENT_TYPE_VARIANT[n.event_type] ?? 'neutral'} className="text-xs">
              {EVENT_TYPE_LABELS[n.event_type] ?? n.event_type}
            </Badge>
            <span className={`text-sm font-medium ${n.is_read ? 'text-text-secondary' : 'text-text-primary'}`}>
              {n.title}
            </span>
          </div>
          {!expanded && (
            <p className="text-xs text-text-muted truncate">{n.body}</p>
          )}
        </div>

        <div className="flex-shrink-0 text-xs text-text-muted whitespace-nowrap">
          {new Date(n.created_at).toLocaleString()}
        </div>
        <span className="text-text-muted text-xs flex-shrink-0">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="border-t border-surface-700 px-5 py-4">
          <pre className="text-sm text-text-secondary whitespace-pre-wrap font-sans">{n.body}</pre>
          {n.read_at && (
            <p className="text-xs text-text-muted mt-3">
              Read at: {new Date(n.read_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'All event types' },
  ...ALL_EVENT_TYPES.map(et => ({ value: et, label: EVENT_TYPE_LABELS[et] })),
]

const UNREAD_OPTIONS = [
  { value: '', label: 'All notifications' },
  { value: '1', label: 'Unread only' },
]

export function InboxPage() {
  const toast = useToast()
  const [unreadFilter, setUnreadFilter] = useState('')
  const [eventTypeFilter, setEventTypeFilter] = useState('')

  const filters = {
    unread: unreadFilter === '1',
    event_type: eventTypeFilter || undefined,
  }

  const { data, isLoading } = useInbox(filters)
  const markReadMut = useMarkRead()
  const markAllMut = useMarkAllRead()

  const notifications = data?.results ?? []

  async function handleMarkRead(id: number) {
    try {
      await markReadMut.mutateAsync(id)
    } catch {
      // Silently ignore — not critical
    }
  }

  async function handleMarkAll() {
    try {
      const result = await markAllMut.mutateAsync()
      toast.success(`Marked ${result.marked_read} notifications as read`)
    } catch {
      toast.error('Failed to mark all as read')
    }
  }

  return (
    <PageWrapper
      title="Notifications"
      subtitle="Your inbox — refreshes every 30 seconds"
      actions={
        <Button
          variant="secondary"
          onClick={() => void handleMarkAll()}
          disabled={markAllMut.isPending}
        >
          Mark all read
        </Button>
      }
    >
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap mb-4">
        <Select
          value={unreadFilter}
          onChange={v => setUnreadFilter(v)}
          options={UNREAD_OPTIONS}
          className="w-44"
        />
        <Select
          value={eventTypeFilter}
          onChange={v => setEventTypeFilter(v)}
          options={EVENT_TYPE_OPTIONS}
          className="w-56"
        />
        <span className="text-sm text-text-muted ml-auto">
          {data?.count ?? 0} notification{data?.count !== 1 ? 's' : ''}
        </span>
      </div>

      {isLoading && (
        <p className="text-sm text-text-muted">Loading…</p>
      )}

      {!isLoading && notifications.length === 0 && (
        <div className="bg-surface-800 border border-surface-700 rounded-xl p-10 text-center text-text-muted text-sm">
          No notifications match your current filters.
        </div>
      )}

      <div className="space-y-2">
        {notifications.map(n => (
          <NotificationRow key={n.id} n={n} onRead={id => void handleMarkRead(id)} />
        ))}
      </div>
    </PageWrapper>
  )
}
