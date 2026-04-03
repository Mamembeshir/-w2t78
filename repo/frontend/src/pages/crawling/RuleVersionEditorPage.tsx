/**
 * RuleVersionEditorPage — Manage rule versions for a crawl source (Phase 6.9).
 *
 * URL: /crawling/rules?source=:id
 *
 * Lists all rule versions for a source.
 * Actions: activate, start canary, rollback canary, create new version.
 */
import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import {
  useSource,
  useRuleVersions,
  useCreateRuleVersion,
  useActivateVersion,
  useStartCanary,
  useRollbackCanary,
  type CrawlRuleVersion,
} from '@/hooks/useCrawling'

function versionBadge(v: CrawlRuleVersion) {
  if (v.is_canary) return <Badge variant="warning">Canary</Badge>
  if (v.is_active) return <Badge variant="success">Active</Badge>
  return <Badge variant="neutral">Inactive</Badge>
}

export function RuleVersionEditorPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const sourceId = Number(params.get('source')) || null
  const toast = useToast()

  const { data: source } = useSource(sourceId)
  const { data: versions, isLoading } = useRuleVersions(sourceId)

  const createMut = useCreateRuleVersion(sourceId ?? 0)
  const activateMut = useActivateVersion(sourceId ?? 0)
  const canaryMut = useStartCanary(sourceId ?? 0)
  const rollbackMut = useRollbackCanary(sourceId ?? 0)

  const [newModalOpen, setNewModalOpen] = useState(false)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  if (!sourceId) {
    return (
      <PageWrapper title="Rule Versions" subtitle="No source selected">
        <Button variant="ghost" onClick={() => navigate('/crawling/sources')}>← Back to Sources</Button>
      </PageWrapper>
    )
  }

  async function handleCreate() {
    if (!note.trim()) return
    setSaving(true)
    try {
      await createMut.mutateAsync({ version_note: note.trim() })
      toast.success('Version created')
      setNote('')
      setNewModalOpen(false)
    } catch {
      toast.error('Create failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleActivate(v: CrawlRuleVersion) {
    try {
      await activateMut.mutateAsync(v.id)
      toast.success(`v${v.version_number} activated`)
    } catch {
      toast.error('Activate failed')
    }
  }

  async function handleCanary(v: CrawlRuleVersion) {
    try {
      await canaryMut.mutateAsync(v.id)
      toast.success(`v${v.version_number} canary started`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      toast.error(msg ?? 'Canary failed')
    }
  }

  async function handleRollback(v: CrawlRuleVersion) {
    try {
      await rollbackMut.mutateAsync(v.id)
      toast.success(`v${v.version_number} rolled back`)
    } catch {
      toast.error('Rollback failed')
    }
  }

  const list = versions?.results ?? []

  return (
    <PageWrapper
      title={source ? `Rule Versions — ${source.name}` : 'Rule Versions'}
      subtitle="Manage crawl rule versions. Activate, canary-test, or rollback."
      actions={
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => navigate('/crawling/sources')}>← Sources</Button>
          <Button onClick={() => setNewModalOpen(true)}>+ New Version</Button>
        </div>
      }
    >
      {isLoading && (
        <p className="text-sm text-text-muted">Loading…</p>
      )}

      {!isLoading && list.length === 0 && (
        <div className="bg-surface-800 border border-surface-700 rounded-xl p-8 text-center text-text-muted text-sm">
          No rule versions yet. Create the first version to enable crawling.
        </div>
      )}

      <div className="space-y-3">
        {list.map(v => (
          <div
            key={v.id}
            className="bg-surface-800 border border-surface-700 rounded-xl p-5 flex items-start justify-between gap-4"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1">
                <span className="text-text-primary font-semibold text-sm">v{v.version_number}</span>
                {versionBadge(v)}
                {v.is_canary && v.canary_error_rate != null && (
                  <span className={`text-xs ${v.canary_error_rate > 2 ? 'text-danger-400' : 'text-success-400'}`}>
                    {v.canary_error_rate.toFixed(1)}% errors
                  </span>
                )}
              </div>
              <p className="text-text-muted text-xs">{v.version_note || '—'}</p>
              {v.canary_started_at && (
                <p className="text-text-muted text-xs mt-1">
                  Canary started: {new Date(v.canary_started_at).toLocaleString()}
                </p>
              )}
              {Object.keys(v.request_headers_masked).length > 0 && (
                <p className="text-text-muted text-xs mt-1">
                  Headers: {Object.keys(v.request_headers_masked).join(', ')} (redacted)
                </p>
              )}
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {!v.is_active && !v.is_canary && (
                <>
                  <Button size="sm" variant="secondary" onClick={() => handleActivate(v)}>
                    Activate
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => handleCanary(v)}>
                    Start Canary
                  </Button>
                </>
              )}
              {v.is_canary && (
                <Button size="sm" variant="danger" onClick={() => handleRollback(v)}>
                  Rollback
                </Button>
              )}
              {v.is_active && !v.is_canary && (
                <span className="text-xs text-success-400 px-2">Current active</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <Modal
        isOpen={newModalOpen}
        onClose={() => setNewModalOpen(false)}
        title="Create New Rule Version"
      >
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Version Note <span className="text-danger-400">*</span></span>
            <Input
              value={note}
              onChange={v => setNote(v)}
              placeholder="e.g. Added pagination support"
            />
          </label>
          <p className="text-xs text-text-muted">
            Version number is auto-incremented. Configure pagination and parameters after creation.
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setNewModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={saving || !note.trim()}>
              {saving ? 'Creating…' : 'Create'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageWrapper>
  )
}
