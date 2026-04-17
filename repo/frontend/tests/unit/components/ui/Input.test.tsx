import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Input } from '@/components/ui/Input'

describe('Input — rendering', () => {
  it('renders without crashing', () => {
    render(<Input />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders a label when label prop is provided', () => {
    render(<Input label="Username" />)
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
  })

  it('shows required asterisk when required prop is set', () => {
    render(<Input label="Field" required />)
    expect(screen.getByText('*')).toBeInTheDocument()
  })

  it('renders help text when provided and no error', () => {
    render(<Input helpText="Enter your full name" />)
    expect(screen.getByText('Enter your full name')).toBeInTheDocument()
  })

  it('hides help text when error is also present', () => {
    render(<Input helpText="Help" error="Required." />)
    expect(screen.queryByText('Help')).not.toBeInTheDocument()
  })

  it('renders prefix node', () => {
    render(<Input prefix={<span>$</span>} />)
    expect(screen.getByText('$')).toBeInTheDocument()
  })

  it('renders suffix node', () => {
    render(<Input suffix={<span>kg</span>} />)
    expect(screen.getByText('kg')).toBeInTheDocument()
  })
})

describe('Input — error state', () => {
  it('shows the error message', () => {
    render(<Input error="This field is required." />)
    expect(screen.getByText('This field is required.')).toBeInTheDocument()
  })

  it('applies danger border class when error is set', () => {
    render(<Input error="Bad" />)
    expect(screen.getByRole('textbox')).toHaveClass('border-danger-500/70')
  })

  it('does not show error icon when no error', () => {
    const { container } = render(<Input />)
    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })
})

describe('Input — interaction', () => {
  it('calls onChange with the string value when user types', async () => {
    const handler = vi.fn()
    render(<Input onChange={handler} />)
    await userEvent.type(screen.getByRole('textbox'), 'hello')
    expect(handler).toHaveBeenLastCalledWith('hello')
  })

  it('is disabled when disabled prop is set', () => {
    render(<Input disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('reflects the controlled value', () => {
    render(<Input value="test" onChange={vi.fn()} />)
    expect(screen.getByRole('textbox')).toHaveValue('test')
  })
})
