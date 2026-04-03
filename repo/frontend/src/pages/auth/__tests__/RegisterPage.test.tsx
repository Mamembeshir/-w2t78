import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RegisterPage } from '../RegisterPage'

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('@/lib/api', () => ({
  api: { post: vi.fn() },
}))

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  )
}

function fillForm({
  username = 'newanalyst',
  email = '',
  password = 'Str0ng!Pass1',
  confirm = 'Str0ng!Pass1',
}: {
  username?: string
  email?: string
  password?: string
  confirm?: string
} = {}) {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: username } })
  if (email) fireEvent.change(screen.getByLabelText(/email/i), { target: { value: email } })
  fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: password } })
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: confirm } })
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('RegisterPage — rendering', () => {
  it('renders the Create account heading', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument()
  })

  it('renders username, email, password, and confirm password fields', () => {
    renderPage()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
  })

  it('renders a link back to /login', () => {
    renderPage()
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login')
  })

  it('renders the submit button', () => {
    renderPage()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
  })
})

describe('RegisterPage — client-side validation', () => {
  beforeEach(() => renderPage())

  it('shows error when username is empty', async () => {
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)
    await waitFor(() => {
      expect(screen.getByText(/username is required/i)).toBeInTheDocument()
    })
  })

  it('shows error when password is empty', async () => {
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'someone' } })
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)
    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument()
    })
  })

  it('shows error when passwords do not match', async () => {
    fillForm({ password: 'Str0ng!Pass1', confirm: 'DifferentPass1!' })
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)
    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    })
  })
})

describe('RegisterPage — API interaction', () => {
  it('calls /api/auth/register/ with username and password on valid submit', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(api.post).mockResolvedValueOnce({ data: { id: 1, username: 'newanalyst', role: 'PROCUREMENT_ANALYST' } })

    renderPage()
    fillForm()
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/', {
        username: 'newanalyst',
        password: 'Str0ng!Pass1',
      })
    })
  })

  it('includes email in the request when provided', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

    renderPage()
    fillForm({ email: 'analyst@example.com' })
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/auth/register/', {
        username: 'newanalyst',
        password: 'Str0ng!Pass1',
        email: 'analyst@example.com',
      })
    })
  })

  it('navigates to /login on success', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(api.post).mockResolvedValueOnce({ data: {} })

    renderPage()
    fillForm()
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true })
    })
  })

  it('shows API error message on failure', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(api.post).mockRejectedValueOnce({
      response: { data: { message: 'A user with that username already exists.' } },
    })

    renderPage()
    fillForm()
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)

    await waitFor(() => {
      expect(screen.getByText(/a user with that username already exists/i)).toBeInTheDocument()
    })
  })

  it('shows fallback error when API gives no message', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(api.post).mockRejectedValueOnce({ response: { data: {} } })

    renderPage()
    fillForm()
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!)

    await waitFor(() => {
      expect(screen.getByText(/registration failed/i)).toBeInTheDocument()
    })
  })
})
