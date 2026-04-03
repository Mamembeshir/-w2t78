/**
 * TaskMonitorPage — Real-time crawl task queue monitor (Phase 6.10).
 *
 * Polls every 5 seconds. Allows filtering by status, retrying FAILED tasks,
 * and enqueueing new tasks.
 */
import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { DataTable } from '@/components/ui/DataTable'
import { Select } from '@/components/ui/Select'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { useSources, useTasks, useEnqueueTask, useRetryTask, type CrawlTask } from '@/hooks/useCrawling'
import type { Column } from '@/types'

const STATUS_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'warning' | 'neutral'> = {
  COMPLETED: 'success', FAILED: 'danger', RUNNING: 'info',
  RETRYING: 'warning', PENDING: 'neutral', WAITING: 'neutral', CANCELLED: 'neutral',
}

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'WAITING', label: 'Waiting' },
  { value: 'RUNNING', label: 'Running' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'RETRYING', label: 'Retrying' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

// Local row type satisfying DataTable's Record<string, unknown> constraint
interface TaskRow extends Record<string, unknown> {
  id: string
  source_name: string
  status: string
  url: string
  attempt_count: string
  created_at: string
  _task_id: string
}

function toRow(t: CrawlTask): TaskRow {
  return {
    id: String(t.id),
    source_name: t.source_name,
    status: t.status,
    url: t.url,
    attempt_count: String(t.attempt_count),
    created_at: t.created_at,
    _task_id: String(t.id),
  }
}

interface EnqueueForm { source_id: string; url: string; priority: string }
const EMPTY_FORM: EnqueueForm = { source_id: '', url: '', priority: '0' }

export function TaskMonitorPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('')
  const { data: tasks, isLoading } = useTasks(statusFilter || undefined)
  const { data: sourcesData } = useSources()
  const retryMut = useRetryTask()
  const enqueueMut = useEnqueueTask()

  // Keep a ref to tasks by id for retry
  const taskMap = new Map<string, CrawlTask>(
    (tasks?.results ?? []).map(t => [String(t.id), t])
  )

  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<EnqueueForm>(EMPTY_FORM)
  const [enqueueing, setEnqueueing] = useState(false)

  const sources = sourcesData?.results ?? []

  async function handleRetry(taskId: string) {
    try {
      await retryMut.mutateAsync(Number(taskId))
      toast.success(`Task #${taskId} re-queued`)
    } catch {
      toast.error('Retry failed')
    }
  }

  async function handleEnqueue() {
    if (!form.source_id || !form.url) return
    setEnqueueing(true)
    try {
      const result = await enqueueMut.mutateAsync({
        source_id: Number(form.source_id),
        url: form.url.trim(),
        priority: Number(form.priority),
      }) as { deduplicated: boolean }
      if (result.deduplicated) {
        toast.info('Duplicate task — returned existing')
      } else {
        toast.success('Task enqueued')
      }
      setModalOpen(false)
      setForm(EMPTY_FORM)
    } catch {
      toast.error('Enqueue failed')
    } finally {
      setEnqueueing(false)
    }
  }

  const COLUMNS: Column<TaskRow>[] = [
    { key: 'id', header: 'ID', sortable: true, className: 'tabular-nums text-text-muted text-xs' },
    { key: 'source_name', header: 'Source', sortable: true },
    {
      key: 'status', header: 'Status', sortable: true,
      render: v => <Badge variant={STATUS_VARIANT[v as string] ?? 'neutral'}>{v as string}</Badge>,
    },
    { key: 'url', header: 'URL', sortable: false, className: 'font-mono text-xs text-text-muted max-w-xs truncate' },
    { key: 'attempt_count', header: 'Attempts', sortable: true, className: 'text-right tabular-nums' },
    {
      key: 'created_at', header: 'Created', sortable: false,
      render: v => new Date(v as string).toLocaleString(),
    },
    {
      key: '_task_id', header: 'Actions', sortable: false,
      render: (v, row) => {
        const t = taskMap.get((row as TaskRow)._task_id)
        return t?.status === 'FAILED' ? (
          <Button size="sm" variant="secondary" onClick={e => { e.stopPropagation(); void handleRetry(v as string) }}>
            Retry
          </Button>
        ) : null
      },
    },
  ]

  const rows = (tasks?.results ?? []).map(toRow)

  return (
    <PageWrapper
      title="Task Monitor"
      subtitle="Live crawl task queue — refreshes every 5 seconds"
      actions={<Button onClick={() => setModalOpen(true)}>+ Enqueue Task</Button>}
    >
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-text-secondary">Filter:</span>
        <Select
          value={statusFilter}
          onChange={v => setStatusFilter(v)}
          options={STATUS_OPTIONS}
          className="w-44"
        />
        <span className="text-sm text-text-muted ml-auto">
          {tasks?.count ?? 0} task{tasks?.count !== 1 ? 's' : ''}
        </span>
      </div>

      <DataTable<TaskRow>
        columns={COLUMNS}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No tasks match the current filter."
      />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Enqueue Crawl Task">
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Source <span className="text-danger-400">*</span></span>
            <Select
              value={form.source_id}
              onChange={v => setForm(f => ({ ...f, source_id: v }))}
              options={[
                { value: '', label: 'Select source…' },
                ...sources.map(s => ({ value: String(s.id), label: s.name })),
              ]}
            />
          </label>
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">URL <span className="text-danger-400">*</span></span>
            <Input
              value={form.url}
              onChange={v => setForm(f => ({ ...f, url: v }))}
              placeholder="https://supplier.local/products"
            />
          </label>
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Priority (lower = higher priority)</span>
            <Input
              type="number"
              value={form.priority}
              onChange={v => setForm(f => ({ ...f, priority: v }))}
            />
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={() => void handleEnqueue()} disabled={enqueueing || !form.source_id || !form.url}>
              {enqueueing ? 'Enqueuing…' : 'Enqueue'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageWrapper>
  )
}
