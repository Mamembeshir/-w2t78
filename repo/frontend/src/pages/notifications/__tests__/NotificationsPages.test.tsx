/**
 * Unit tests for notification module pages: InboxPage.
 *
 * All hook calls are mocked at the module boundary.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ── Shared mocks ──────────────────────────────────────────────────────────────

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/hooks/useNotifications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/useNotifications')>()
  return {
    ...actual,           // re-export constants (ALL_EVENT_TYPES, EVENT_TYPE_LABELS)
    useInbox:       vi.fn(),
    useMarkRead:    vi.fn(),
    useMarkAllRead: vi.fn(),
  }
})

import {
  useInbox, useMarkRead, useMarkAllRead,
} from '@/hooks/useNotifications'

const NOOP_MUTATION = { isPending: false, mutateAsync: vi.fn() }

// ── InboxPage ─────────────────────────────────────────────────────────────────

import { InboxPage } from '../InboxPage'

const MOCK_NOTIFICATION_UNREAD = {
  id: 1,
  event_type: 'SAFETY_STOCK_BREACH' as const,
  title: 'Low stock on SKU-001',
  body:  'Quantity on hand (3) is below safety stock (10).',
  is_read:    false,
  read_at:    null,
  created_at: '2026-01-01T10:00:00Z',
}

const MOCK_NOTIFICATION_READ = {
  id: 2,
  event_type: 'SYSTEM' as const,
  title: 'Scheduled maintenance',
  body:  'System will be offline at 2 AM UTC.',
  is_read:    true,
  read_at:    '2026-01-01T11:00:00Z',
  created_at: '2026-01-01T09:00:00Z',
}

describe('InboxPage — loading state', () => {
  beforeEach(() => {
    vi.mocked(useInbox).mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useInbox>)
    vi.mocked(useMarkRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkRead>)
    vi.mocked(useMarkAllRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkAllRead>)
  })

  it('renders page title', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('Notifications')).toBeInTheDocument()
  })

  it('shows Loading text while fetching', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><InboxPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('InboxPage — empty state', () => {
  beforeEach(() => {
    vi.mocked(useInbox).mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useInbox>)
    vi.mocked(useMarkRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkRead>)
    vi.mocked(useMarkAllRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkAllRead>)
  })

  it('shows empty-state message', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(
      screen.getByText('No notifications match your current filters.'),
    ).toBeInTheDocument()
  })

  it('shows 0 notifications count', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('0 notifications')).toBeInTheDocument()
  })

  it('renders filter dropdowns', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('All notifications')).toBeInTheDocument()
    expect(screen.getByText('All event types')).toBeInTheDocument()
  })

  it('shows Mark all read button', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Mark all read' })).toBeInTheDocument()
  })
})

describe('InboxPage — with notifications', () => {
  beforeEach(() => {
    vi.mocked(useInbox).mockReturnValue({
      data: { count: 2, results: [MOCK_NOTIFICATION_UNREAD, MOCK_NOTIFICATION_READ] },
      isLoading: false,
    } as ReturnType<typeof useInbox>)
    vi.mocked(useMarkRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkRead>)
    vi.mocked(useMarkAllRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkAllRead>)
  })

  it('shows correct notification count', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('2 notifications')).toBeInTheDocument()
  })

  it('renders unread notification title', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('Low stock on SKU-001')).toBeInTheDocument()
  })

  it('renders read notification title', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    expect(screen.getByText('Scheduled maintenance')).toBeInTheDocument()
  })

  it('renders event type badge for unread notification', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    // 'Safety Stock Breach' also appears in the event-type filter <option> — use getAllByText
    expect(screen.getAllByText('Safety Stock Breach')[0]).toBeInTheDocument()
  })

  it('expands notification body on click', () => {
    render(<MemoryRouter><InboxPage /></MemoryRouter>)
    // Click the first notification row to expand it
    const firstTitle = screen.getByText('Low stock on SKU-001')
    fireEvent.click(firstTitle.closest('[class*="border"]')!)
    expect(screen.getByText('Quantity on hand (3) is below safety stock (10).')).toBeInTheDocument()
  })
})

describe('InboxPage — graceful null handling', () => {
  it('does not crash when data is null', () => {
    vi.mocked(useInbox).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useInbox>)
    vi.mocked(useMarkRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkRead>)
    vi.mocked(useMarkAllRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkAllRead>)

    expect(() => render(<MemoryRouter><InboxPage /></MemoryRouter>)).not.toThrow()
  })

  it('does not crash when results is missing from response', () => {
    vi.mocked(useInbox).mockReturnValue({
      data: { count: 0 } as never,
      isLoading: false,
    } as ReturnType<typeof useInbox>)
    vi.mocked(useMarkRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkRead>)
    vi.mocked(useMarkAllRead).mockReturnValue(NOOP_MUTATION as ReturnType<typeof useMarkAllRead>)

    expect(() => render(<MemoryRouter><InboxPage /></MemoryRouter>)).not.toThrow()
  })
})
