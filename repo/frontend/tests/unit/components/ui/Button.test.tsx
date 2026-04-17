import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '@/components/ui/Button'

describe('Button — rendering', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })

  it('defaults to primary variant and md size', () => {
    const { container } = render(<Button>Primary</Button>)
    const btn = container.firstChild as HTMLElement
    expect(btn).toHaveClass('bg-primary-500')
    expect(btn).toHaveClass('px-4')
  })

  it('renders secondary variant', () => {
    const { container } = render(<Button variant="secondary">Sec</Button>)
    expect(container.firstChild).toHaveClass('bg-surface-700/80')
  })

  it('renders danger variant', () => {
    const { container } = render(<Button variant="danger">Del</Button>)
    expect(container.firstChild).toHaveClass('bg-danger-500')
  })

  it('renders ghost variant', () => {
    const { container } = render(<Button variant="ghost">Ghost</Button>)
    expect(container.firstChild).toHaveClass('text-text-secondary')
  })

  it('renders sm size', () => {
    const { container } = render(<Button size="sm">Small</Button>)
    expect(container.firstChild).toHaveClass('px-3')
  })

  it('renders lg size', () => {
    const { container } = render(<Button size="lg">Large</Button>)
    expect(container.firstChild).toHaveClass('px-6')
  })

  it('applies additional className', () => {
    const { container } = render(<Button className="w-full">Wide</Button>)
    expect(container.firstChild).toHaveClass('w-full')
  })
})

describe('Button — disabled state', () => {
  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('does not call onClick when disabled', async () => {
    const handler = vi.fn()
    render(<Button disabled onClick={handler}>Disabled</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(handler).not.toHaveBeenCalled()
  })
})

describe('Button — loading state', () => {
  it('is disabled when loading is true', () => {
    render(<Button loading>Save</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('renders a spinner when loading', () => {
    const { container } = render(<Button loading>Save</Button>)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('still shows children text while loading', () => {
    render(<Button loading>Saving</Button>)
    expect(screen.getByText('Saving')).toBeInTheDocument()
  })
})

describe('Button — interaction', () => {
  it('calls onClick when clicked', async () => {
    const handler = vi.fn()
    render(<Button onClick={handler}>Go</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(handler).toHaveBeenCalledOnce()
  })

  it('forwards type attribute', () => {
    render(<Button type="submit">Submit</Button>)
    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit')
  })
})
