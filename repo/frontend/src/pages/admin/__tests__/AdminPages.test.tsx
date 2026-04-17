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
  useUsers:       vi.fn(),
  useCreateUser:  vi.fn(),
  useUpdateUser:  vi.fn(),
  useAuditLog:    vi.fn(),
  useHealthCheck: vi.fn(),
}))

import {
  useUsers, useCreateUser, useUpdateUser,
  useAuditLog, useHealthCheck,
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

// ── AdminDashboard ─────────────────────────────────────────────────────────────

import { AdminDashboard } from '../AdminDashboard'

const MOCK_USER = {
  id: 1, username: 'admin', email: 'admin@local', first_name: 'Ad', last_name: 'Min',
  role: 'ADMIN', is_active: true, last_login: null, date_joined: '2026-01-01T00:00:00Z',
}

const MOCK_AUDIT_ENTRY = {
  id: 1, user: 'admin', action: 'CREATE', model_name: 'Item',
  object_id: '42', changes: {}, ip_address: '127.0.0.1',
  timestamp: '2026-01-01T10:00:00Z',
}

function setupDashboard({
  usersData = undefined as unknown,
  auditData = undefined as unknown,
  health = undefined as unknown,
  loading = false,
} = {}) {
  vi.mocked(useUsers).mockReturnValue({ data: usersData, isLoading: loading } as ReturnType<typeof useUsers>)
  vi.mocked(useAuditLog).mockReturnValue({ data: auditData, isLoading: loading } as ReturnType<typeof useAuditLog>)
  vi.mocked(useHealthCheck).mockReturnValue({ data: health, isLoading: loading } as ReturnType<typeof useHealthCheck>)
}

describe('AdminDashboard — loading state', () => {
  beforeEach(() => setupDashboard({ loading: true }))

  it('renders page title', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('Admin Dashboard')).toBeInTheDocument()
  })

  it('shows Total Users stat card label', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('Total Users')).toBeInTheDocument()
  })

  it('shows Audit Entries stat card label', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('Audit Entries')).toBeInTheDocument()
  })

  it('shows System Status stat card label', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('System Status')).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><AdminDashboard /></MemoryRouter>)).not.toThrow()
  })
})

describe('AdminDashboard — with data', () => {
  beforeEach(() => setupDashboard({
    usersData: { count: 3, results: [MOCK_USER] },
    auditData: { count: 12, results: [MOCK_AUDIT_ENTRY] },
    health: { status: 'ok', db: 'ok', redis: 'ok' },
  }))

  it('shows total user count in stat card', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows audit entry count in stat card', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('shows OK system status', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('OK')).toBeInTheDocument()
  })

  it('shows DB and Redis status in health sublabel', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('DB: ok · Redis: ok')).toBeInTheDocument()
  })

  it('renders username in users table', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    // 'admin' appears in both the username and role columns — use getAllByText
    expect(screen.getAllByText('admin')[0]).toBeInTheDocument()
  })

  it('renders audit action badge in audit table', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('CREATE')).toBeInTheDocument()
  })
})

describe('AdminDashboard — degraded health', () => {
  beforeEach(() => setupDashboard({
    usersData: { count: 0, results: [] },
    auditData: { count: 0, results: [] },
    health: { status: 'degraded', db: 'ok', redis: 'error' },
  }))

  it('shows Degraded system status', () => {
    render(<MemoryRouter><AdminDashboard /></MemoryRouter>)
    expect(screen.getByText('Degraded')).toBeInTheDocument()
  })
})

describe('AdminDashboard — graceful null handling', () => {
  it('does not crash when all data is null', () => {
    setupDashboard({ usersData: null, auditData: null, health: null })
    expect(() => render(<MemoryRouter><AdminDashboard /></MemoryRouter>)).not.toThrow()
  })

  it('does not crash when results is missing', () => {
    setupDashboard({
      usersData: { count: 0 } as never,
      auditData: { count: 0 } as never,
      health: null,
    })
    expect(() => render(<MemoryRouter><AdminDashboard /></MemoryRouter>)).not.toThrow()
  })
})
