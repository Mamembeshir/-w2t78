/**
 * Smoke tests for admin pages — verify each page renders without crashing
 * in loading, empty-data, and error (404 / unexpected shape) states.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ── Shared mocks ──────────────────────────────────────────────────────────────

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

// ── useAdmin mocks ─────────────────────────────────────────────────────────────

vi.mock('@/hooks/useAdmin', () => ({
  useUsers:      vi.fn(),
  useCreateUser: vi.fn(),
  useUpdateUser: vi.fn(),
  useAuditLog:   vi.fn(),
}))

import {
  useUsers, useCreateUser, useUpdateUser,
  useAuditLog,
} from '@/hooks/useAdmin'

const PENDING_MUTATION = { isPending: false, mutateAsync: vi.fn() }

// ── UserManagementPage ─────────────────────────────────────────────────────────

import { UserManagementPage } from '../UserManagementPage'

describe('UserManagementPage — smoke tests', () => {
  function setup(data: unknown, isLoading = false) {
    vi.mocked(useUsers).mockReturnValue({ data, isLoading } as ReturnType<typeof useUsers>)
    vi.mocked(useCreateUser).mockReturnValue(PENDING_MUTATION as ReturnType<typeof useCreateUser>)
    vi.mocked(useUpdateUser).mockReturnValue(PENDING_MUTATION as ReturnType<typeof useUpdateUser>)
  }

  it('renders while loading without crash', () => {
    setup(undefined, true)
    expect(() => render(<MemoryRouter><UserManagementPage /></MemoryRouter>)).not.toThrow()
    expect(screen.getByText('User Management')).toBeInTheDocument()
  })

  it('renders with empty results without crash', () => {
    setup({ count: 0, results: [] })
    expect(() => render(<MemoryRouter><UserManagementPage /></MemoryRouter>)).not.toThrow()
    expect(screen.getByText('No users found.')).toBeInTheDocument()
  })

  it('renders with populated results', () => {
    setup({
      count: 1,
      results: [{
        id: 1, username: 'admin', first_name: 'Ad', last_name: 'Min',
        email: 'admin@local', role: 'ADMIN', is_active: true,
        last_login: null, date_joined: '2026-01-01T00:00:00Z',
      }],
    })
    render(<MemoryRouter><UserManagementPage /></MemoryRouter>)
    expect(screen.getByText('admin')).toBeInTheDocument()
  })

  it('does not crash when data.results is missing (unexpected API shape)', () => {
    setup({ count: 0 } as never)
    expect(() => render(<MemoryRouter><UserManagementPage /></MemoryRouter>)).not.toThrow()
  })

  it('does not crash when data is null (network error scenario)', () => {
    setup(null)
    expect(() => render(<MemoryRouter><UserManagementPage /></MemoryRouter>)).not.toThrow()
  })

  it('shows user count in subtitle', () => {
    setup({ count: 7, results: [] })
    render(<MemoryRouter><UserManagementPage /></MemoryRouter>)
    expect(screen.getByText('7 users total')).toBeInTheDocument()
  })
})

// ── AuditLogPage ──────────────────────────────────────────────────────────────

import { AuditLogPage } from '../AuditLogPage'

describe('AuditLogPage — smoke tests', () => {
  function setup(data: unknown, isLoading = false) {
    vi.mocked(useAuditLog).mockReturnValue({ data, isLoading } as ReturnType<typeof useAuditLog>)
  }

  it('renders while loading without crash', () => {
    setup(undefined, true)
    expect(() => render(<MemoryRouter><AuditLogPage /></MemoryRouter>)).not.toThrow()
    expect(screen.getByText('Audit Log')).toBeInTheDocument()
  })

  it('renders empty state without crash', () => {
    setup({ count: 0, results: [] })
    expect(() => render(<MemoryRouter><AuditLogPage /></MemoryRouter>)).not.toThrow()
    expect(screen.getByText(/No audit log entries/)).toBeInTheDocument()
  })

  it('does not crash when data is null', () => {
    setup(null)
    expect(() => render(<MemoryRouter><AuditLogPage /></MemoryRouter>)).not.toThrow()
  })

  it('does not crash when results is missing', () => {
    setup({ count: 0 } as never)
    expect(() => render(<MemoryRouter><AuditLogPage /></MemoryRouter>)).not.toThrow()
  })
})
