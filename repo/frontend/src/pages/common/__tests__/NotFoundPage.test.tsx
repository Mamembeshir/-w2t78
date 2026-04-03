import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { NotFoundPage } from '../NotFoundPage'

// Default: unauthenticated
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({ user: null })),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>,
  )
}

describe('NotFoundPage — unauthenticated', () => {
  it('renders the 404 heading', () => {
    renderPage()
    expect(screen.getByText('404')).toBeInTheDocument()
  })

  it('renders the "Page not found" message', () => {
    renderPage()
    expect(screen.getByText('Page not found')).toBeInTheDocument()
  })

  it('links to /login when no user is logged in', () => {
    renderPage()
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute('href', '/login')
  })
})

describe('NotFoundPage — authenticated', () => {
  it('links to /inventory for INVENTORY_MANAGER', async () => {
    const { useAuth } = await import('@/hooks/useAuth')
    vi.mocked(useAuth).mockReturnValue({ user: { role: 'INVENTORY_MANAGER' } } as ReturnType<typeof useAuth>)

    renderPage()
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute('href', '/inventory')
  })

  it('links to /admin for ADMIN', async () => {
    const { useAuth } = await import('@/hooks/useAuth')
    vi.mocked(useAuth).mockReturnValue({ user: { role: 'ADMIN' } } as ReturnType<typeof useAuth>)

    renderPage()
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute('href', '/admin')
  })

  it('links to /crawling for PROCUREMENT_ANALYST', async () => {
    const { useAuth } = await import('@/hooks/useAuth')
    vi.mocked(useAuth).mockReturnValue({ user: { role: 'PROCUREMENT_ANALYST' } } as ReturnType<typeof useAuth>)

    renderPage()
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute('href', '/crawling')
  })
})
