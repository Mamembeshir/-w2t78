import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from '@/components/ui/Modal'

function renderModal(props: Partial<React.ComponentProps<typeof Modal>> = {}) {
  return render(
    <Modal
      isOpen={true}
      onClose={vi.fn()}
      title="Test Modal"
      {...props}
    >
      <p>Modal body</p>
    </Modal>,
  )
}

describe('Modal — open/closed state', () => {
  it('renders content when isOpen is true', () => {
    renderModal({ isOpen: true })
    expect(screen.getByText('Test Modal')).toBeInTheDocument()
    expect(screen.getByText('Modal body')).toBeInTheDocument()
  })

  it('renders nothing when isOpen is false', () => {
    renderModal({ isOpen: false })
    expect(screen.queryByText('Test Modal')).not.toBeInTheDocument()
    expect(screen.queryByText('Modal body')).not.toBeInTheDocument()
  })

  it('has role="dialog" and aria-modal', () => {
    renderModal()
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })

  it('labels the dialog with the title', () => {
    renderModal({ title: 'Confirm Delete' })
    expect(screen.getByRole('dialog', { name: 'Confirm Delete' })).toBeInTheDocument()
  })
})

describe('Modal — close behaviour', () => {
  it('calls onClose when the close button is clicked', async () => {
    const onClose = vi.fn()
    renderModal({ onClose })
    await userEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when the backdrop is clicked', async () => {
    const onClose = vi.fn()
    const { container } = renderModal({ onClose })
    // The backdrop is the second div (absolute overlay)
    const backdrop = container.querySelector('[aria-hidden="true"]') as HTMLElement
    await userEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when Escape key is pressed', async () => {
    const onClose = vi.fn()
    renderModal({ onClose })
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })
})

describe('Modal — footer', () => {
  it('renders footer content when footer prop is provided', () => {
    renderModal({ footer: <button>Confirm</button> })
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
  })

  it('does not render a footer section when footer prop is omitted', () => {
    const { container } = renderModal()
    // Only the close button should be present (no extra footer buttons)
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveAttribute('aria-label', 'Close')
  })
})

describe('Modal — size', () => {
  it('applies max-w-md for sm size', () => {
    const { container } = renderModal({ size: 'sm' })
    expect(container.querySelector('.max-w-md')).toBeInTheDocument()
  })

  it('applies max-w-2xl for lg size', () => {
    const { container } = renderModal({ size: 'lg' })
    expect(container.querySelector('.max-w-2xl')).toBeInTheDocument()
  })

  it('defaults to max-w-lg (md)', () => {
    const { container } = renderModal()
    expect(container.querySelector('.max-w-lg')).toBeInTheDocument()
  })
})
