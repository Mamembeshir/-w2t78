import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '../ProtectedRoute'

// ── Mock useAuth ──────────────────────────────────────────────────────────────

vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/hooks/useAuth'

function setUser(user: Parameters<typeof useAuth>[0] extends never ? unknown : ReturnType<typeof useAuth>['user']) {
  vi.mocked(useAuth).mockReturnValue({
    user,
    isLoading: false,
  } as ReturnType<typeof useAuth>)
}

// ── Render helpers ────────────────────────────────────────────────────────────

function renderRoute(allowedRoles?: string[]) {
  return render(
    <MemoryRouter initialEntries={['/protected']}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/admin" element={<div>Admin Dashboard</div>} />
        <Route path="/inventory" element={<div>Inventory Dashboard</div>} />
        <Route path="/crawling" element={<div>Crawling Dashboard</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute allowedRoles={allowedRoles as never}>
              <div>Protected Content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ProtectedRoute — unauthenticated', () => {
  it('redirects to /login when user is null', () => {
    setUser(null)
    renderRoute()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})

describe('ProtectedRoute — authenticated, no role restriction', () => {
  it('renders children when user is logged in and no allowedRoles set', () => {
    setUser({ role: 'INVENTORY_MANAGER' } as never)
    renderRoute()
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })
})

describe('ProtectedRoute — role guard', () => {
  it('renders children when user role is in allowedRoles', () => {
    setUser({ role: 'ADMIN' } as never)
    renderRoute(['ADMIN'])
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('redirects to role dashboard when user role is not in allowedRoles', () => {
    setUser({ role: 'INVENTORY_MANAGER' } as never)
    renderRoute(['ADMIN'])
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.getByText('Inventory Dashboard')).toBeInTheDocument()
  })

  it('redirects PROCUREMENT_ANALYST to /crawling when role not allowed', () => {
    setUser({ role: 'PROCUREMENT_ANALYST' } as never)
    renderRoute(['ADMIN'])
    expect(screen.getByText('Crawling Dashboard')).toBeInTheDocument()
  })

  it('redirects ADMIN to /admin when role not allowed', () => {
    setUser({ role: 'ADMIN' } as never)
    renderRoute(['INVENTORY_MANAGER'])
    expect(screen.getByText('Admin Dashboard')).toBeInTheDocument()
  })

  it('allows access when user has one of multiple allowed roles', () => {
    setUser({ role: 'INVENTORY_MANAGER' } as never)
    renderRoute(['ADMIN', 'INVENTORY_MANAGER'])
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })
})

describe('ProtectedRoute — loading state', () => {
  it('renders a spinner while auth state is loading', () => {
    vi.mocked(useAuth).mockReturnValue({ user: null, isLoading: true } as ReturnType<typeof useAuth>)
    const { container } = renderRoute()
    // LoadingSpinner renders an SVG
    expect(container.querySelector('svg')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})
