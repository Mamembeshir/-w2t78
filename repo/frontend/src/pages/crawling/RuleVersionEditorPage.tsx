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
  useTestRuleVersion,
  type CrawlRuleVersion,
  type RuleTestResult,
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
  const testMut = useTestRuleVersion()

  const [newModalOpen, setNewModalOpen] = useState(false)
  const [testResult, setTestResult] = useState<{ versionId: number; result: RuleTestResult } | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [urlPattern, setUrlPattern] = useState('')
  const [parametersJson, setParametersJson] = useState('')
  const [paginationJson, setPaginationJson] = useState('')
  const [headersJson, setHeadersJson] = useState('')
  const [jsonErrors, setJsonErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  if (!sourceId) {
    return (
      <PageWrapper title="Rule Versions" subtitle="No source selected">
        <Button variant="ghost" onClick={() => navigate('/crawling/sources')}>← Back to Sources</Button>
      </PageWrapper>
    )
  }

  function validateJson(raw: string, field: string): unknown | null {
    if (!raw.trim()) return null
    try {
      return JSON.parse(raw)
    } catch {
      setJsonErrors(prev => ({ ...prev, [field]: 'Invalid JSON' }))
      return undefined // sentinel: parse failed
    }
  }

  async function handleCreate() {
    if (!note.trim() || !urlPattern.trim()) return
    setJsonErrors({})

    const params = parametersJson.trim() ? validateJson(parametersJson, 'parameters') : null
    const pagination = paginationJson.trim() ? validateJson(paginationJson, 'pagination_config') : null
    if (params === undefined || pagination === undefined) return // JSON error

    setSaving(true)
    try {
      const payload: Parameters<typeof createMut.mutateAsync>[0] = {
        version_note: note.trim(),
        url_pattern: urlPattern.trim(),
      }
      if (params !== null) payload.parameters = params
      if (pagination !== null) payload.pagination_config = pagination
      if (headersJson.trim()) payload.request_headers = headersJson.trim()

      await createMut.mutateAsync(payload)
      toast.success('Version created')
      setNote('')
      setUrlPattern('')
      setParametersJson('')
      setPaginationJson('')
      setHeadersJson('')
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

  async function handleTest(v: CrawlRuleVersion) {
    setTestingId(v.id)
    setTestResult(null)
    try {
      const result = await testMut.mutateAsync(v.id)
      setTestResult({ versionId: v.id, result })
    } catch {
      toast.error('Test request failed')
    } finally {
      setTestingId(null)
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
          <div key={v.id}>
            <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 flex items-start justify-between gap-4">
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
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => testResult?.versionId === v.id ? setTestResult(null) : handleTest(v)}
                  disabled={testingId === v.id}
                >
                  {testingId === v.id ? 'Testing…' : 'Test'}
                </Button>
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

            {/* Test result panel */}
            {testResult?.versionId === v.id && (
              <div className={`border border-t-0 rounded-b-xl px-5 py-4 text-sm ${
                testResult.result.error
                  ? 'bg-danger-950 border-danger-700'
                  : testResult.result.status_code && testResult.result.status_code < 400
                    ? 'bg-success-950 border-success-700'
                    : 'bg-warning-950 border-warning-700'
              }`}>
                <div className="flex items-center gap-4 mb-2 font-mono text-xs">
                  {testResult.result.status_code != null && (
                    <span className={`font-semibold ${
                      testResult.result.status_code < 400 ? 'text-success-400' : 'text-danger-400'
                    }`}>
                      HTTP {testResult.result.status_code}
                    </span>
                  )}
                  <span className="text-text-muted">{testResult.result.duration_ms} ms</span>
                  {testResult.result.error && (
                    <span className="text-danger-400">{testResult.result.error}</span>
                  )}
                </div>
                {testResult.result.snippet && (
                  <pre className="text-text-secondary text-xs bg-surface-900 rounded p-3 overflow-x-auto whitespace-pre-wrap break-all max-h-40">
                    {testResult.result.snippet}
                  </pre>
                )}
              </div>
            )}
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

          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">URL Pattern <span className="text-danger-400">*</span></span>
            <Input
              value={urlPattern}
              onChange={v => setUrlPattern(v)}
              placeholder="e.g. /products/{id} or https://supplier.local/catalog"
            />
            <span className="text-xs text-text-muted mt-1 block">
              Template URL for this rule. Use {'{param}'} placeholders for dynamic segments.
            </span>
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Parameters <span className="text-text-muted">(optional JSON object)</span></span>
            <textarea
              value={parametersJson}
              onChange={e => setParametersJson(e.target.value)}
              placeholder={'{\n  "category": "electronics"\n}'}
              rows={3}
              className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-text-primary font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            {jsonErrors.parameters && (
              <span className="text-xs text-danger-400 mt-1 block">{jsonErrors.parameters}</span>
            )}
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Pagination Config <span className="text-text-muted">(optional JSON object)</span></span>
            <textarea
              value={paginationJson}
              onChange={e => setPaginationJson(e.target.value)}
              placeholder={'{\n  "type": "page",\n  "page_param": "page",\n  "page_size": 50\n}'}
              rows={4}
              className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-text-primary font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            {jsonErrors.pagination_config && (
              <span className="text-xs text-danger-400 mt-1 block">{jsonErrors.pagination_config}</span>
            )}
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary mb-1 block">Request Headers <span className="text-text-muted">(optional — stored encrypted)</span></span>
            <textarea
              value={headersJson}
              onChange={e => setHeadersJson(e.target.value)}
              placeholder={'{\n  "Authorization": "Bearer <token>"\n}'}
              rows={3}
              className="w-full bg-surface-700 border border-surface-600 rounded-lg px-3 py-2 text-sm text-text-primary font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <span className="text-xs text-text-muted mt-1 block">
              Must be a flat JSON object of string key/value pairs. Values are encrypted at rest and masked in the UI.
            </span>
          </label>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setNewModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={saving || !note.trim() || !urlPattern.trim()}>
              {saving ? 'Creating…' : 'Create'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageWrapper>
  )
}
