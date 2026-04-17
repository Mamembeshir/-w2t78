/**
 * Smoke tests for SystemSettingsPage.
 *
 * The page makes direct api.get / api.patch / api.post calls (no React Query hook).
 * We mock the api module to control loading and data states.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/lib/api', () => ({
  api: {
    get:   vi.fn(),
    patch: vi.fn(),
    post:  vi.fn(),
  },
}))

import { api } from '@/lib/api'

const MOCK_SETTINGS = {
  smtp_host: 'smtp.example.com',
  smtp_port: 587,
  smtp_use_tls: true,
  sms_gateway_url: 'https://sms.example.com/send',
}

describe('SystemSettingsPage — loading (api not resolved)', () => {
  beforeEach(() => {
    // Return a pending promise so the page stays in its loading / default state
    vi.mocked(api.get).mockReturnValue(new Promise(() => {}) as never)
  })

  it('renders page title', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)
    expect(screen.getByText(/System Settings/i)).toBeInTheDocument()
  })

  it('renders SMTP section heading', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'SMTP Gateway' })).toBeInTheDocument()
  })

  it('renders SMS section heading', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'SMS Gateway' })).toBeInTheDocument()
  })

  it('does not crash on initial render', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    expect(() => render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('SystemSettingsPage — with loaded settings', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({ data: MOCK_SETTINGS })
    vi.mocked(api.patch).mockResolvedValue({ data: MOCK_SETTINGS })
    vi.mocked(api.post).mockResolvedValue({ data: {} })
  })

  it('renders Save button', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Save Settings' })).toBeInTheDocument()
  })

  it('renders Test SMTP button', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Test SMTP Connection' })).toBeInTheDocument()
  })

  it('renders Test SMS button', async () => {
    const { SystemSettingsPage } = await import('../SystemSettingsPage')
    render(<MemoryRouter><SystemSettingsPage /></MemoryRouter>)
    expect(screen.getByRole('button', { name: 'Test SMS Gateway' })).toBeInTheDocument()
  })
})
