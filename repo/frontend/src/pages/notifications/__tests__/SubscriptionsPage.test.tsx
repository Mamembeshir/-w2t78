/**
 * Smoke tests for SubscriptionsPage (notification preferences).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/hooks/useNotifications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/useNotifications')>()
  return {
    ...actual,
    useSubscriptions:         vi.fn(),
    useSubscribe:             vi.fn(),
    useUnsubscribe:           vi.fn(),
    useDigestSchedule:        vi.fn(),
    useUpdateDigestSchedule:  vi.fn(),
  }
})

import {
  useSubscriptions, useSubscribe, useUnsubscribe,
  useDigestSchedule, useUpdateDigestSchedule,
} from '@/hooks/useNotifications'

import { SubscriptionsPage } from '../SubscriptionsPage'

const NOOP = { isPending: false, mutateAsync: vi.fn() }
const MOCK_SUBSCRIPTION = {
  id: 1,
  event_type: 'SAFETY_STOCK_BREACH' as const,
  threshold_value: '10',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}
const MOCK_DIGEST = {
  id: 1,
  send_time: '08:00:00',
  is_active: true,
  last_sent_at: '2026-01-01T08:00:00Z',
}

function setup(opts: {
  loading?: boolean
  subscriptions?: typeof MOCK_SUBSCRIPTION[]
  digest?: typeof MOCK_DIGEST | null
} = {}) {
  vi.mocked(useSubscriptions).mockReturnValue({
    data: opts.loading ? undefined : { count: opts.subscriptions?.length ?? 0, results: opts.subscriptions ?? [] },
    isLoading: opts.loading ?? false,
  } as ReturnType<typeof useSubscriptions>)
  vi.mocked(useDigestSchedule).mockReturnValue({
    data: opts.loading ? undefined : (opts.digest ?? null),
    isLoading: opts.loading ?? false,
  } as ReturnType<typeof useDigestSchedule>)
  vi.mocked(useSubscribe).mockReturnValue(NOOP as ReturnType<typeof useSubscribe>)
  vi.mocked(useUnsubscribe).mockReturnValue(NOOP as ReturnType<typeof useUnsubscribe>)
  vi.mocked(useUpdateDigestSchedule).mockReturnValue(NOOP as ReturnType<typeof useUpdateDigestSchedule>)
}

describe('SubscriptionsPage — loading', () => {
  beforeEach(() => setup({ loading: true }))

  it('renders page title', () => {
    render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)
    expect(screen.getByText('Notification Settings')).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('SubscriptionsPage — empty subscriptions', () => {
  beforeEach(() => setup({ digest: MOCK_DIGEST }))

  it('shows empty subscriptions state', () => {
    render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)
    expect(screen.getByText(/No active subscriptions/i)).toBeInTheDocument()
  })

  it('shows Add Subscription button', () => {
    render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)
    expect(screen.getByText('+ Subscribe')).toBeInTheDocument()
  })

  it('shows digest send time', () => {
    render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Daily Digest' })).toBeInTheDocument()
  })
})

describe('SubscriptionsPage — with subscriptions', () => {
  beforeEach(() => setup({ subscriptions: [MOCK_SUBSCRIPTION], digest: MOCK_DIGEST }))

  it('renders active subscription event type', () => {
    render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)
    expect(screen.getByText('Safety Stock Breach')).toBeInTheDocument()
  })

  it('shows Remove button for active subscription', () => {
    render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /Remove/i })).toBeInTheDocument()
  })
})

describe('SubscriptionsPage — null handling', () => {
  it('does not crash when data is null', () => {
    vi.mocked(useSubscriptions).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useSubscriptions>)
    vi.mocked(useDigestSchedule).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useDigestSchedule>)
    vi.mocked(useSubscribe).mockReturnValue(NOOP as ReturnType<typeof useSubscribe>)
    vi.mocked(useUnsubscribe).mockReturnValue(NOOP as ReturnType<typeof useUnsubscribe>)
    vi.mocked(useUpdateDigestSchedule).mockReturnValue(NOOP as ReturnType<typeof useUpdateDigestSchedule>)
    expect(() => render(<MemoryRouter><SubscriptionsPage /></MemoryRouter>)).not.toThrow()
  })
})
