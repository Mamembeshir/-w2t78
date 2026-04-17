/**
 * Smoke tests for crawling editor/utility pages:
 * RuleVersionEditorPage and RequestDebuggerPage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// ── Shared mocks ──────────────────────────────────────────────────────────────

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

vi.mock('@/hooks/useCrawling', () => ({
  useSources:           vi.fn(),
  useSource:            vi.fn(),
  useRuleVersions:      vi.fn(),
  useCreateRuleVersion: vi.fn(),
  useActivateVersion:   vi.fn(),
  useStartCanary:       vi.fn(),
  useRollbackCanary:    vi.fn(),
  useTestRuleVersion:   vi.fn(),
  useDebugLog:          vi.fn(),
}))

import {
  useSources, useSource, useRuleVersions,
  useCreateRuleVersion, useActivateVersion,
  useStartCanary, useRollbackCanary, useTestRuleVersion,
  useDebugLog,
} from '@/hooks/useCrawling'

const NOOP = { isPending: false, mutateAsync: vi.fn() }
const EMPTY = { data: { count: 0, results: [] }, isLoading: false }
const LOADING = { data: undefined, isLoading: true }

const MOCK_SOURCE = {
  id: 1, name: 'Supplier A', base_url: 'http://supplier.local',
  rate_limit_rpm: 60, crawl_delay_seconds: 1,
  honor_local_crawl_delay: true, user_agents: [],
  is_active: true, active_rule_version: null,
  created_by: null, created_at: '2026-01-01T00:00:00Z',
}

const MOCK_RULE_VERSION = {
  id: 1, source: 1, version_number: 1,
  version_note: 'Initial version',
  url_pattern: 'http://supplier.local/products',
  parameters: null, pagination_config: null,
  is_active: true, is_canary: false,
  canary_pct: 0, canary_started_at: null, canary_error_rate: null,
  request_headers_masked: {},
  created_by: null, created_at: '2026-01-01T00:00:00Z',
}

// ── RuleVersionEditorPage ─────────────────────────────────────────────────────

import { RuleVersionEditorPage } from '@/pages/crawling/RuleVersionEditorPage'

function renderEditor(sourceId: string) {
  return render(
    <MemoryRouter initialEntries={[`/crawling/rules?source=${sourceId}`]}>
      <Routes>
        <Route path="/crawling/rules" element={<RuleVersionEditorPage />} />
        <Route path="/crawling" element={<div>Crawling Home</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function setupEditor(opts: { loading?: boolean; withData?: boolean } = {}) {
  const src = opts.loading ? LOADING : {
    data: opts.withData ? MOCK_SOURCE : null,
    isLoading: false,
  }
  const versions = opts.loading ? LOADING : {
    data: opts.withData ? { count: 1, results: [MOCK_RULE_VERSION] } : { count: 0, results: [] },
    isLoading: false,
  }
  vi.mocked(useSource).mockReturnValue(src as ReturnType<typeof useSource>)
  vi.mocked(useRuleVersions).mockReturnValue(versions as ReturnType<typeof useRuleVersions>)
  vi.mocked(useCreateRuleVersion).mockReturnValue(NOOP as ReturnType<typeof useCreateRuleVersion>)
  vi.mocked(useActivateVersion).mockReturnValue(NOOP as ReturnType<typeof useActivateVersion>)
  vi.mocked(useStartCanary).mockReturnValue(NOOP as ReturnType<typeof useStartCanary>)
  vi.mocked(useRollbackCanary).mockReturnValue(NOOP as ReturnType<typeof useRollbackCanary>)
  vi.mocked(useTestRuleVersion).mockReturnValue(NOOP as ReturnType<typeof useTestRuleVersion>)
}

describe('RuleVersionEditorPage — loading', () => {
  beforeEach(() => setupEditor({ loading: true }))

  it('renders page title', () => {
    renderEditor('1')
    expect(screen.getByRole('heading', { name: /Rule Versions/i })).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => renderEditor('1')).not.toThrow()
  })
})

describe('RuleVersionEditorPage — with source and versions', () => {
  beforeEach(() => setupEditor({ withData: true }))

  it('shows source name in header', () => {
    renderEditor('1')
    expect(screen.getByText(/Supplier A/i)).toBeInTheDocument()
  })

  it('renders rule version number', () => {
    renderEditor('1')
    expect(screen.getByText(/v1/i)).toBeInTheDocument()
  })

  it('shows New Version button', () => {
    renderEditor('1')
    expect(screen.getByText(/New Version/i)).toBeInTheDocument()
  })
})

describe('RuleVersionEditorPage — empty versions', () => {
  beforeEach(() => setupEditor())

  it('does not crash with no versions', () => {
    expect(() => renderEditor('1')).not.toThrow()
  })

  it('shows New Version button when no versions exist', () => {
    renderEditor('1')
    expect(screen.getByText(/New Version/i)).toBeInTheDocument()
  })
})

// ── RequestDebuggerPage ───────────────────────────────────────────────────────

import { RequestDebuggerPage } from '@/pages/crawling/RequestDebuggerPage'

const MOCK_LOG = {
  id: 1,
  source: 1,
  url: 'http://supplier.local/products?page=1',
  status_code: 200,
  duration_ms: 342,
  request_headers: { 'User-Agent': 'WarehouseBot/1.0' },
  response_snippet: '<html><body>Products</body></html>',
  created_at: '2026-01-01T10:00:00Z',
}

function setupDebugger(opts: { loading?: boolean; withLogs?: boolean } = {}) {
  vi.mocked(useSources).mockReturnValue(
    opts.loading
      ? (LOADING as ReturnType<typeof useSources>)
      : { data: { count: 1, results: [MOCK_SOURCE] }, isLoading: false } as ReturnType<typeof useSources>,
  )
  vi.mocked(useDebugLog).mockReturnValue(
    opts.loading
      ? (LOADING as ReturnType<typeof useDebugLog>)
      : {
          data: opts.withLogs ? { count: 1, results: [MOCK_LOG] } : { count: 0, results: [] },
          isLoading: false,
        } as ReturnType<typeof useDebugLog>,
  )
}

describe('RequestDebuggerPage — loading', () => {
  beforeEach(() => setupDebugger({ loading: true }))

  it('renders page title', () => {
    render(<MemoryRouter><RequestDebuggerPage /></MemoryRouter>)
    expect(screen.getByText(/Request Debugger/i)).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><RequestDebuggerPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('RequestDebuggerPage — source selection prompt', () => {
  beforeEach(() => setupDebugger())

  it('shows source selector dropdown', () => {
    render(<MemoryRouter><RequestDebuggerPage /></MemoryRouter>)
    expect(screen.getByText('Select a source…')).toBeInTheDocument()
  })

  it('shows prompt to select a source', () => {
    render(<MemoryRouter><RequestDebuggerPage /></MemoryRouter>)
    expect(screen.getByText('Select a source above to view its request logs.')).toBeInTheDocument()
  })
})

describe('RequestDebuggerPage — null handling', () => {
  it('does not crash when sources are null', () => {
    vi.mocked(useSources).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useSources>)
    vi.mocked(useDebugLog).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useDebugLog>)
    expect(() => render(<MemoryRouter><RequestDebuggerPage /></MemoryRouter>)).not.toThrow()
  })
})
