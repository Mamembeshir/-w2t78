import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockLogin = vi.fn()
const mockNavigate = vi.fn()

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ login: mockLogin }),
}))

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

// ── Helpers ───────────────────────────────────────────────────────────────────

import { LoginPage } from '@/pages/auth/LoginPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('LoginPage — rendering', () => {
  it('renders the sign-in heading', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })

  it('renders username and password inputs', () => {
    renderPage()
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('renders the submit button', () => {
    renderPage()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('renders a link to the register page', () => {
    renderPage()
    expect(screen.getByRole('link', { name: /create account/i })).toHaveAttribute('href', '/register')
  })
})

describe('LoginPage — client-side validation', () => {
  it('shows an error when username is empty', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(screen.getByText('Username is required.')).toBeInTheDocument()
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('shows an error when password is empty', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText(/username/i), 'admin')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(mockLogin).not.toHaveBeenCalled()
  })
})

describe('LoginPage — successful login', () => {
  it('calls login with trimmed username and password', async () => {
    mockLogin.mockResolvedValue(undefined)
    renderPage()
    await userEvent.type(screen.getByLabelText(/username/i), '  admin  ')
    await userEvent.type(screen.getByLabelText(/password/i), 'secret')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('admin', 'secret'))
  })

  it('navigates to / on success', async () => {
    mockLogin.mockResolvedValue(undefined)
    renderPage()
    await userEvent.type(screen.getByLabelText(/username/i), 'admin')
    await userEvent.type(screen.getByLabelText(/password/i), 'secret')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }))
  })
})

describe('LoginPage — failed login', () => {
  it('shows invalid credentials error when login rejects', async () => {
    mockLogin.mockRejectedValue(new Error('401'))
    renderPage()
    await userEvent.type(screen.getByLabelText(/username/i), 'admin')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() =>
      expect(screen.getByText('Invalid username or password.')).toBeInTheDocument(),
    )
  })

  it('does not navigate when login fails', async () => {
    mockLogin.mockRejectedValue(new Error('401'))
    renderPage()
    await userEvent.type(screen.getByLabelText(/username/i), 'admin')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(screen.getByText('Invalid username or password.')).toBeInTheDocument())
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})
