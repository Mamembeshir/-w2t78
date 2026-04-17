/**
 * Unit tests for crawling module pages: SourcesPage and TaskMonitorPage.
 *
 * All hook calls are mocked at the module boundary so tests are fast and
 * deterministic — no HTTP, no React Query providers required.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ── Shared mocks ──────────────────────────────────────────────────────────────

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn() }
})

// ── useCrawling mock ───────────────────────────────────────────────────────────

vi.mock('@/hooks/useCrawling', () => ({
  useSources:     vi.fn(),
  useCreateSource: vi.fn(),
  useUpdateSource: vi.fn(),
  useTasks:        vi.fn(),
  useEnqueueTask:  vi.fn(),
  useRetryTask:    vi.fn(),
}))

import {
  useSources, useCreateSource, useUpdateSource,
  useTasks, useEnqueueTask, useRetryTask,
} from '@/hooks/useCrawling'

const NOOP_MUTATION = { isPending: false, mutateAsync: vi.fn() }

// ── SourcesPage ────────────────────────────────────────────────────────────────

import { SourcesPage } from '../SourcesPage'

const MOCK_SOURCE = {
  id: 1,
  name: 'Supplier A',
  base_url: 'http://supplier-a.local',
  rate_limit_rpm: 60,
  crawl_delay_seconds: 1,
  honor_local_crawl_delay: true,
  user_agents: ['Bot/1.0'],
  is_active: true,
  active_rule_version: 2,
  created_by: null,
  created_at: '2026-01-01T00:00:00Z',
}

describe('SourcesPage — loading state', () => {
  beforeEach(() => {
    vi.mocked(useSources).mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useSources>)
    vi.mocked(useCreateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useCreateSource>)
    vi.mocked(useUpdateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useUpdateSource>)
  })

  it('renders page title', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('Crawl Sources')).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><SourcesPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('SourcesPage — empty state', () => {
  beforeEach(() => {
    vi.mocked(useSources).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useSources>)
    vi.mocked(useCreateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useCreateSource>)
    vi.mocked(useUpdateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useUpdateSource>)
  })

  it('shows empty-state message', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('No crawl sources configured.')).toBeInTheDocument()
  })

  it('shows the New Source button', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('+ New Source')).toBeInTheDocument()
  })
})

describe('SourcesPage — with data', () => {
  beforeEach(() => {
    vi.mocked(useSources).mockReturnValue({
      data: { count: 1, results: [MOCK_SOURCE] },
      isLoading: false,
    } as ReturnType<typeof useSources>)
    vi.mocked(useCreateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useCreateSource>)
    vi.mocked(useUpdateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useUpdateSource>)
  })

  it('renders source name in table', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('Supplier A')).toBeInTheDocument()
  })

  it('renders base URL in table', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('http://supplier-a.local')).toBeInTheDocument()
  })

  it('renders Active badge for active source', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows Edit button for each source', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    expect(screen.getByText('Edit Supplier A')).toBeInTheDocument()
  })
})

describe('SourcesPage — modal', () => {
  beforeEach(() => {
    vi.mocked(useSources).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useSources>)
    vi.mocked(useCreateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useCreateSource>)
    vi.mocked(useUpdateSource).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useUpdateSource>)
  })

  it('opens "New Crawl Source" modal on button click', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    fireEvent.click(screen.getByText('+ New Source'))
    expect(screen.getByText('New Crawl Source')).toBeInTheDocument()
  })

  it('Save button is disabled when name and base_url are empty', () => {
    render(<MemoryRouter><SourcesPage /></MemoryRouter>)
    fireEvent.click(screen.getByText('+ New Source'))
    // Save button should be disabled: no name, no base_url filled in
    const saveBtn = screen.getByRole('button', { name: 'Save' })
    expect(saveBtn).toBeDisabled()
  })
})

// ── TaskMonitorPage ────────────────────────────────────────────────────────────

import { TaskMonitorPage } from '../TaskMonitorPage'

const MOCK_TASK_PENDING = {
  id: 10,
  source: 1,
  source_name: 'Supplier A',
  rule_version: null,
  fingerprint: 'abc123',
  url: 'http://supplier-a.local/products',
  status: 'PENDING' as const,
  priority: 0,
  attempt_count: 0,
  last_error: '',
  checkpoint_page: 0,
  next_retry_at: null,
  started_at: null,
  completed_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

const MOCK_TASK_FAILED = {
  ...MOCK_TASK_PENDING,
  id: 11,
  status: 'FAILED' as const,
  attempt_count: 3,
  last_error: 'Connection refused',
}

describe('TaskMonitorPage — loading state', () => {
  beforeEach(() => {
    vi.mocked(useTasks).mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useTasks>)
    vi.mocked(useSources).mockReturnValue({ data: undefined, isLoading: false } as ReturnType<typeof useSources>)
    vi.mocked(useRetryTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useRetryTask>)
    vi.mocked(useEnqueueTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useEnqueueTask>)
  })

  it('renders page title', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    expect(screen.getByText('Task Monitor')).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('TaskMonitorPage — empty state', () => {
  beforeEach(() => {
    vi.mocked(useTasks).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useTasks>)
    vi.mocked(useSources).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useSources>)
    vi.mocked(useRetryTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useRetryTask>)
    vi.mocked(useEnqueueTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useEnqueueTask>)
  })

  it('shows empty-state message', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    expect(screen.getByText('No tasks match the current filter.')).toBeInTheDocument()
  })

  it('shows task count as 0 tasks', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    expect(screen.getByText('0 tasks')).toBeInTheDocument()
  })
})

describe('TaskMonitorPage — with data', () => {
  beforeEach(() => {
    vi.mocked(useTasks).mockReturnValue({
      data: { count: 2, results: [MOCK_TASK_PENDING, MOCK_TASK_FAILED] },
      isLoading: false,
    } as ReturnType<typeof useTasks>)
    vi.mocked(useSources).mockReturnValue({
      data: { count: 1, results: [MOCK_SOURCE] },
      isLoading: false,
    } as ReturnType<typeof useSources>)
    vi.mocked(useRetryTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useRetryTask>)
    vi.mocked(useEnqueueTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useEnqueueTask>)
  })

  it('shows correct task count', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    expect(screen.getByText('2 tasks')).toBeInTheDocument()
  })

  it('renders PENDING badge', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    // 'PENDING' also appears as a <option> in the status filter — use getAllByText
    expect(screen.getAllByText('PENDING')[0]).toBeInTheDocument()
  })

  it('renders FAILED badge', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    // 'FAILED' also appears as a <option> in the status filter — use getAllByText
    expect(screen.getAllByText('FAILED')[0]).toBeInTheDocument()
  })

  it('shows Retry button for FAILED task', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('does not show Retry button for PENDING task', () => {
    // Only 1 Retry button should appear (for the FAILED task, not the PENDING one)
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    expect(screen.getAllByRole('button', { name: 'Retry' })).toHaveLength(1)
  })
})

describe('TaskMonitorPage — enqueue modal', () => {
  beforeEach(() => {
    vi.mocked(useTasks).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useTasks>)
    vi.mocked(useSources).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useSources>)
    vi.mocked(useRetryTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useRetryTask>)
    vi.mocked(useEnqueueTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useEnqueueTask>)
  })

  it('opens Enqueue Task modal on button click', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    fireEvent.click(screen.getByText('+ Enqueue Task'))
    expect(screen.getByText('Enqueue Crawl Task')).toBeInTheDocument()
  })

  it('Enqueue button is disabled when no source or URL provided', () => {
    render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)
    fireEvent.click(screen.getByText('+ Enqueue Task'))
    expect(screen.getByRole('button', { name: 'Enqueue' })).toBeDisabled()
  })
})

describe('TaskMonitorPage — graceful null handling', () => {
  it('does not crash when data is null', () => {
    vi.mocked(useTasks).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useTasks>)
    vi.mocked(useSources).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useSources>)
    vi.mocked(useRetryTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useRetryTask>)
    vi.mocked(useEnqueueTask).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useEnqueueTask>)

    expect(() => render(<MemoryRouter><TaskMonitorPage /></MemoryRouter>)).not.toThrow()
  })
})
