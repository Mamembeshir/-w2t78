import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { DataTable } from '@/components/ui/DataTable'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useAuditLog } from '@/hooks/useAdmin'
import type { AuditEntry } from '@/hooks/useAdmin'
import type { Column } from '@/types'

interface AuditRow extends Record<string, unknown> {
  id: string
  user: string
  action: string
  model_name: string
  object_id: string
  ip_address: string
  timestamp: string
}

const ACTION_OPTIONS = [
  { value: '', label: 'All actions' },
  { value: 'CREATE', label: 'Create' },
  { value: 'UPDATE', label: 'Update' },
  { value: 'DELETE', label: 'Delete' },
]

const ACTION_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  CREATE: 'success',
  UPDATE: 'warning',
  DELETE: 'danger',
}

const COLUMNS: Column<AuditRow>[] = [
  {
    key: 'timestamp',
    header: 'Time',
    sortable: true,
    render: (v) => new Date(v as string).toLocaleString(),
  },
  {
    key: 'user',
    header: 'User',
    sortable: true,
    className: 'font-medium text-text-primary',
  },
  {
    key: 'action',
    header: 'Action',
    sortable: true,
    render: (v) => (
      <Badge variant={ACTION_VARIANT[String(v)] ?? 'neutral'}>{String(v)}</Badge>
    ),
  },
  {
    key: 'model_name',
    header: 'Model',
    sortable: true,
  },
  {
    key: 'object_id',
    header: 'Object ID',
    sortable: false,
    className: 'font-mono text-xs',
  },
  {
    key: 'ip_address',
    header: 'IP Address',
    sortable: false,
    className: 'font-mono text-xs',
    render: (v) => (v as string | null) ?? '—',
  },
]

export function AuditLogPage() {
  const [model, setModel] = useState('')
  const [action, setAction] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const params = {
    ...(model ? { model } : {}),
    ...(action ? { action } : {}),
    ...(fromDate ? { from_date: fromDate } : {}),
    ...(toDate ? { to_date: toDate } : {}),
  }

  const { data, isLoading } = useAuditLog(params)

  const rows: AuditRow[] = (data?.results ?? []).map((e: AuditEntry) => ({
    id: String(e.id),
    user: e.user,
    action: e.action,
    model_name: e.model_name,
    object_id: e.object_id,
    ip_address: e.ip_address ?? '—',
    timestamp: e.timestamp,
  }))

  return (
    <PageWrapper
      title="Audit Log"
      subtitle={`${data?.count ?? 0} entries`}
    >
      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <Input
          label="Model"
          placeholder="e.g. Item, CrawlSource"
          value={model}
          onChange={setModel}
          className="w-52"
        />
        <Select
          label="Action"
          options={ACTION_OPTIONS}
          value={action}
          onChange={setAction}
          className="w-44"
        />
        <Input
          label="From date"
          type="date"
          value={fromDate}
          onChange={setFromDate}
          className="w-44"
        />
        <Input
          label="To date"
          type="date"
          value={toDate}
          onChange={setToDate}
          className="w-44"
        />
      </div>

      <DataTable<AuditRow>
        columns={COLUMNS}
        rows={rows}
        rowKey="id"
        isLoading={isLoading}
        emptyMessage="No audit log entries match the current filters."
      />
    </PageWrapper>
  )
}
