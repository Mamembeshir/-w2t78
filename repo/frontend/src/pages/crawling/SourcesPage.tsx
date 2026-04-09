/**
 * SourcesPage — Crawl Source Configuration Center (Phase 6.8).
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { DataTable } from '@/components/ui/DataTable'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { useSources, useCreateSource, useUpdateSource, type CrawlSource } from '@/hooks/useCrawling'
import type { Column } from '@/types'

// Local row type satisfying DataTable's Record<string, unknown> constraint
interface SourceRow extends Record<string, unknown> {
  id: string
  name: string
  base_url: string
  rate_limit_rpm: string
  crawl_delay_seconds: string
  active_rule_version: string
  is_active: string
  _raw: CrawlSource
}

const COLUMNS: Column<SourceRow>[] = [
  { key: 'name', header: 'Name', sortable: true },
  { key: 'base_url', header: 'Base URL', sortable: false, className: 'font-mono text-xs text-text-muted max-w-xs truncate' },
  { key: 'rate_limit_rpm', header: 'RPM Limit', sortable: true, className: 'text-right tabular-nums', render: v => <span className="text-primary-400">{v as string}</span> },
  { key: 'crawl_delay_seconds', header: 'Delay (s)', sortable: true, className: 'text-right tabular-nums' },
  {
    key: 'active_rule_version', header: 'Active Version', sortable: false,
    render: v => (v as string) !== 'none'
      ? <span className="text-success-400 font-mono text-xs">v{v as string}</span>
      : <span className="text-text-muted text-xs">none</span>,
  },
  {
    key: 'is_active', header: 'Status', sortable: true,
    render: v => <Badge variant={(v as string) === 'true' ? 'success' : 'neutral'}>{(v as string) === 'true' ? 'Active' : 'Disabled'}</Badge>,
  },
]

function toRow(s: CrawlSource): SourceRow {
  return {
    id: String(s.id),
    name: s.name,
    base_url: s.base_url,
    rate_limit_rpm: String(s.rate_limit_rpm),
    crawl_delay_seconds: String(s.crawl_delay_seconds),
    active_rule_version: s.active_rule_version != null ? String(s.active_rule_version) : 'none',
    is_active: String(s.is_active),
    _raw: s,
  }
}

interface SourceForm {
  name: string
  base_url: string
  rate_limit_rpm: string
  crawl_delay_seconds: string
  honor_local_crawl_delay: boolean
  /** One user-agent string per line; validated and split on save */
  user_agents_text: string
}

const EMPTY_FORM: SourceForm = {
  name: '',
  base_url: '',
  rate_limit_rpm: '60',
  crawl_delay_seconds: '1',
  honor_local_crawl_delay: true,
  user_agents_text: '',
}

export function SourcesPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useSources()
  const createMut = useCreateSource()
  const [editTarget, setEditTarget] = useState<CrawlSource | null>(null)
  const updateMut = useUpdateSource(editTarget?.id ?? 0)
  const toast = useToast()

  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<SourceForm>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [uaError, setUaError] = useState('')

  function openCreate() {
    setEditTarget(null)
    setForm(EMPTY_FORM)
    setUaError('')
    setModalOpen(true)
  }

  function openEdit(src: CrawlSource) {
    setEditTarget(src)
    setForm({
      name: src.name,
      base_url: src.base_url,
      rate_limit_rpm: String(src.rate_limit_rpm),
      crawl_delay_seconds: String(src.crawl_delay_seconds),
      honor_local_crawl_delay: src.honor_local_crawl_delay,
      user_agents_text: (src.user_agents ?? []).join('\n'),
    })
    setUaError('')
    setModalOpen(true)
  }

  async function handleSave() {
    setUaError('')
    const rawLines = form.user_agents_text.split('\n').map(l => l.trim()).filter(Boolean)
    const invalidLine = rawLines.find(l => l.length === 0)
    if (invalidLine !== undefined) {
      setUaError('Each line must be a non-empty user-agent string.')
      return
    }

    setSaving(true)
    const payload = {
      name: form.name.trim(),
      base_url: form.base_url.trim(),
      rate_limit_rpm: Number(form.rate_limit_rpm),
      crawl_delay_seconds: Number(form.crawl_delay_seconds),
      honor_local_crawl_delay: form.honor_local_crawl_delay,
      user_agents: rawLines,
    }
    try {
      if (editTarget) {
        await updateMut.mutateAsync(payload)
        toast.success('Source updated')
      } else {
        await createMut.mutateAsync(payload)
        toast.success('Source created')
      }
      setModalOpen(false)
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  const rows = (data?.results ?? []).map(toRow)

  return (
    <PageWrapper
      title="Crawl Sources"
      subtitle="Configure data sources and their crawl rules"
      actions={<Button onClick={openCreate}>+ New Source</Button>}
    >
      <DataTable<SourceRow>
        columns={COLUMNS}
        data={rows}
        isLoading={isLoading}
        emptyMessage="No crawl sources configured."
        onRowClick={row => {
          if (row._raw) navigate(`/crawling/rules?source=${row._raw.id}`)
        }}
      />

      {/* Edit buttons row — shown below table */}
      {rows.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {(data?.results ?? []).map(src => (
            <Button
              key={src.id}
              size="sm"
              variant="ghost"
              onClick={() => openEdit(src)}
            >
              Edit {src.name}
            </Button>
          ))}
        </div>
      )}

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editTarget ? 'Edit Source' : 'New Crawl Source'}
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Name <span className="text-danger-400">*</span></span>
            <Input
              value={form.name}
              onChange={v => setForm(f => ({ ...f, name: v }))}
              placeholder="e.g. Supplier A"
            />
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Base URL <span className="text-danger-400">*</span></span>
            <Input
              value={form.base_url}
              onChange={v => setForm(f => ({ ...f, base_url: v }))}
              placeholder="https://supplier.local/api"
            />
          </label>

          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="text-sm text-text-secondary mb-1 block">Rate Limit (RPM)</span>
              <Input
                type="number"
                min={1}
                value={form.rate_limit_rpm}
                onChange={v => setForm(f => ({ ...f, rate_limit_rpm: v }))}
              />
            </label>
            <label className="block">
              <span className="text-sm text-text-secondary mb-1 block">Crawl Delay (sec)</span>
              <Input
                type="number"
                min={0}
                step={0.5}
                value={form.crawl_delay_seconds}
                onChange={v => setForm(f => ({ ...f, crawl_delay_seconds: v }))}
              />
            </label>
          </div>

          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              className="w-4 h-4 rounded accent-primary-500"
              checked={form.honor_local_crawl_delay}
              onChange={e => setForm(f => ({ ...f, honor_local_crawl_delay: e.target.checked }))}
            />
            <span className="text-sm text-text-secondary">
              Honor crawl delay from local ruleset
              <span className="block text-xs text-text-muted">
                When enabled, the worker sleeps between pages per the configured delay (CLAUDE.md §9).
              </span>
            </span>
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">
              User-Agent Rotation List
              <span className="text-text-muted font-normal"> (optional — one per line)</span>
            </span>
            <textarea
              value={form.user_agents_text}
              onChange={e => { setForm(f => ({ ...f, user_agents_text: e.target.value })); setUaError('') }}
              rows={4}
              placeholder={"Mozilla/5.0 (compatible; WarehouseBot/1.0)\nMozilla/5.0 (Windows NT 10.0; Win64; x64)"}
              className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-text-primary font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            {uaError && <span className="text-xs text-danger-400 mt-1 block">{uaError}</span>}
            <span className="text-xs text-text-muted mt-1 block">
              The crawler rotates through these strings randomly. Leave blank to send no User-Agent header.
            </span>
          </label>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.name || !form.base_url}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageWrapper>
  )
}
