/**
 * RequestDebuggerPage — Visual request/response debugger (Phase 6.11).
 *
 * Shows the last 20 CrawlRequestLog entries for a selected source.
 * Refreshes every 10 seconds.
 */
import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { useSources, useDebugLog, type CrawlRequestLog } from '@/hooks/useCrawling'

function statusVariant(code: number | null): 'success' | 'danger' | 'warning' | 'neutral' {
  if (code == null) return 'neutral'
  if (code >= 200 && code < 300) return 'success'
  if (code >= 400 && code < 500) return 'warning'
  if (code >= 500) return 'danger'
  return 'neutral'
}

function LogEntry({ log }: { log: CrawlRequestLog }) {
  const [expanded, setExpanded] = useState(false)

  let headersObj: Record<string, string> = {}
  try { headersObj = JSON.parse(log.request_headers) } catch { /* noop */ }

  return (
    <div
      className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden cursor-pointer hover:border-surface-600 transition-colors"
      onClick={() => setExpanded(e => !e)}
    >
      {/* Summary row */}
      <div className="px-5 py-3 flex items-center gap-3">
        <Badge variant={statusVariant(log.response_status)}>
          {log.response_status ?? '—'}
        </Badge>
        <span className="font-mono text-xs text-text-primary flex-1 truncate">{log.request_url}</span>
        <span className="text-xs text-text-muted tabular-nums">{log.duration_ms} ms</span>
        <span className="text-xs text-text-muted">{new Date(log.timestamp).toLocaleTimeString()}</span>
        <span className="text-text-muted text-xs">{expanded ? '▲' : '▼'}</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-surface-700 px-5 py-4 space-y-4">
          <div>
            <p className="text-xs font-semibold text-text-secondary mb-1">Request Headers</p>
            <pre className="text-xs text-text-muted bg-surface-900 rounded-lg p-3 overflow-x-auto">
              {Object.entries(headersObj).length > 0
                ? Object.entries(headersObj).map(([k, v]) => `${k}: ${v}`).join('\n')
                : '(none)'}
            </pre>
          </div>
          {log.response_snippet && (
            <div>
              <p className="text-xs font-semibold text-text-secondary mb-1">Response Snippet (first 500 chars)</p>
              <pre className="text-xs text-text-muted bg-surface-900 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                {log.response_snippet}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function RequestDebuggerPage() {
  const { data: sourcesData, isLoading: sourcesLoading } = useSources()
  const [sourceId, setSourceId] = useState<number | null>(null)
  const { data: logs, isLoading: logsLoading } = useDebugLog(sourceId)

  const sources = sourcesData?.results ?? []

  return (
    <PageWrapper
      title="Request Debugger"
      subtitle="Last 20 HTTP request/response samples per source — refreshes every 10 seconds"
    >
      <div className="flex items-center gap-3 mb-6">
        <span className="text-sm text-text-secondary">Source:</span>
        {sourcesLoading ? (
          <span className="text-sm text-text-muted">Loading sources…</span>
        ) : (
          <Select
            value={sourceId != null ? String(sourceId) : ''}
            onChange={v => setSourceId(v ? Number(v) : null)}
            options={[
              { value: '', label: 'Select a source…' },
              ...sources.map(s => ({ value: String(s.id), label: s.name })),
            ]}
            className="w-64"
          />
        )}
      </div>

      {!sourceId && (
        <div className="bg-surface-800 border border-surface-700 rounded-xl p-8 text-center text-text-muted text-sm">
          Select a source above to view its request logs.
        </div>
      )}

      {sourceId && logsLoading && (
        <p className="text-sm text-text-muted">Loading logs…</p>
      )}

      {sourceId && !logsLoading && (logs == null || logs.length === 0) && (
        <div className="bg-surface-800 border border-surface-700 rounded-xl p-8 text-center text-text-muted text-sm">
          No request logs yet for this source.
        </div>
      )}

      {logs && logs.length > 0 && (
        <div className="space-y-2">
          {logs.map(log => (
            <LogEntry key={log.id} log={log} />
          ))}
        </div>
      )}
    </PageWrapper>
  )
}
