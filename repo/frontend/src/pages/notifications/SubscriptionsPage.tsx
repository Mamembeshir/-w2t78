/**
 * SubscriptionsPage — Notification subscription settings (Phase 7.7).
 *
 * URL: /notifications/settings
 *
 * Features:
 * - List active subscriptions with remove button
 * - Add new subscription by event type
 * - Digest schedule toggle (update send_time or disable)
 */
import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import {
  useSubscriptions,
  useSubscribe,
  useUnsubscribe,
  useDigestSchedule,
  useUpdateDigestSchedule,
  ALL_EVENT_TYPES,
  EVENT_TYPE_LABELS,
  type EventType,
} from '@/hooks/useNotifications'

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

export function SubscriptionsPage() {
  const toast = useToast()

  const { data: subsData, isLoading: subsLoading } = useSubscriptions()
  const subscribeMut = useSubscribe()
  const unsubscribeMut = useUnsubscribe()
  const { data: digestSchedule, isLoading: digestLoading } = useDigestSchedule()
  const updateDigestMut = useUpdateDigestSchedule()

  const [addModalOpen, setAddModalOpen] = useState(false)
  const [newEventType, setNewEventType] = useState<EventType>('SAFETY_STOCK_BREACH')
  const [newThreshold, setNewThreshold] = useState('')
  const [adding, setAdding] = useState(false)

  const [digestTime, setDigestTime] = useState('')
  const [updatingDigest, setUpdatingDigest] = useState(false)

  const subs = subsData?.results ?? []

  // Event types not yet subscribed
  const subscribedTypes = new Set(subs.map(s => s.event_type))
  const availableTypes = ALL_EVENT_TYPES.filter(et => !subscribedTypes.has(et) && et !== 'DIGEST')

  async function handleAdd() {
    setAdding(true)
    try {
      await subscribeMut.mutateAsync({
        event_type: newEventType,
        threshold_value: newThreshold || undefined,
      })
      toast.success(`Subscribed to ${EVENT_TYPE_LABELS[newEventType]}`)
      setAddModalOpen(false)
      setNewThreshold('')
    } catch {
      toast.error('Subscribe failed')
    } finally {
      setAdding(false)
    }
  }

  async function handleRemove(id: number, eventType: EventType) {
    try {
      await unsubscribeMut.mutateAsync(id)
      toast.success(`Unsubscribed from ${EVENT_TYPE_LABELS[eventType]}`)
    } catch {
      toast.error('Unsubscribe failed')
    }
  }

  async function handleUpdateDigest() {
    if (!digestTime) return
    setUpdatingDigest(true)
    try {
      await updateDigestMut.mutateAsync({ send_time: digestTime + ':00' })
      toast.success('Digest schedule updated')
    } catch {
      toast.error('Update failed')
    } finally {
      setUpdatingDigest(false)
    }
  }

  return (
    <PageWrapper
      title="Notification Settings"
      subtitle="Manage your subscriptions and daily digest schedule"
    >
      {/* Subscriptions */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Active Subscriptions</h2>
          <Button
            size="sm"
            onClick={() => {
              if (availableTypes.length > 0) setNewEventType(availableTypes[0]!)
              setAddModalOpen(true)
            }}
            disabled={availableTypes.length === 0}
          >
            + Subscribe
          </Button>
        </div>

        {subsLoading && <p className="px-5 py-4 text-sm text-text-muted">Loading…</p>}

        {!subsLoading && subs.length === 0 && (
          <p className="px-5 py-6 text-sm text-text-muted text-center">
            No active subscriptions. Click "+ Subscribe" to add one.
          </p>
        )}

        <div className="divide-y divide-surface-700">
          {subs.map(sub => (
            <div key={sub.id} className="px-5 py-3 flex items-center gap-3">
              <Badge variant={EVENT_TYPE_VARIANT[sub.event_type] ?? 'neutral'}>
                {EVENT_TYPE_LABELS[sub.event_type] ?? sub.event_type}
              </Badge>
              {sub.threshold_value != null && (
                <span className="text-xs text-text-muted">threshold: {sub.threshold_value}</span>
              )}
              <span className="text-xs text-text-muted ml-auto">
                since {new Date(sub.created_at).toLocaleDateString()}
              </span>
              <Button
                size="sm"
                variant="danger"
                onClick={() => void handleRemove(sub.id, sub.event_type)}
              >
                Remove
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Daily digest schedule */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-4">Daily Digest</h2>
        {digestLoading ? (
          <p className="text-sm text-text-muted">Loading…</p>
        ) : (
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <p className="text-xs text-text-secondary mb-1">
                Current send time:{' '}
                <span className="text-text-primary font-mono">
                  {digestSchedule?.send_time ?? '18:00'}
                </span>
              </p>
              {digestSchedule?.last_sent_at && (
                <p className="text-xs text-text-muted">
                  Last sent: {new Date(digestSchedule.last_sent_at).toLocaleString()}
                </p>
              )}
            </div>
            <div className="flex items-end gap-2">
              <label className="block">
                <span className="text-xs text-text-secondary mb-1 block">New send time (HH:MM)</span>
                <Input
                  type="time"
                  value={digestTime}
                  onChange={v => setDigestTime(v)}
                  className="w-36"
                />
              </label>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void handleUpdateDigest()}
                disabled={updatingDigest || !digestTime}
              >
                {updatingDigest ? 'Saving…' : 'Update'}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Add subscription modal */}
      <Modal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        title="Subscribe to Event Type"
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Event Type <span className="text-danger-400">*</span></span>
            <Select
              value={newEventType}
              onChange={v => setNewEventType(v as EventType)}
              options={availableTypes.map(et => ({ value: et, label: EVENT_TYPE_LABELS[et] }))}
            />
          </label>
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Threshold (optional — e.g. minimum quantity for stock alerts)</span>
            <Input
              type="number"
              value={newThreshold}
              onChange={v => setNewThreshold(v)}
              placeholder="e.g. 100"
            />
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setAddModalOpen(false)}>Cancel</Button>
            <Button onClick={() => void handleAdd()} disabled={adding}>
              {adding ? 'Subscribing…' : 'Subscribe'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageWrapper>
  )
}
