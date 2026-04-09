import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge, RoleBadge } from '../Badge'

describe('Badge — variants', () => {
  const variants = ['success', 'warning', 'danger', 'info', 'neutral', 'primary'] as const

  it.each(variants)('renders %s variant without crashing', (variant) => {
    render(<Badge variant={variant}>Label</Badge>)
    expect(screen.getByText('Label')).toBeInTheDocument()
  })

  it('defaults to neutral when no variant supplied', () => {
    const { container } = render(<Badge>Default</Badge>)
    expect(container.firstChild).toHaveClass('bg-surface-700')
  })

  it('applies additional className', () => {
    const { container } = render(<Badge className="extra-class">Hi</Badge>)
    expect(container.firstChild).toHaveClass('extra-class')
  })

  it('renders children correctly', () => {
    render(<Badge variant="success">Active</Badge>)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })
})

describe('RoleBadge', () => {
  it('renders Admin label for ADMIN role', () => {
    render(<RoleBadge role="ADMIN" />)
    expect(screen.getByText('Admin')).toBeInTheDocument()
  })

  it('renders Inv. Manager label for INVENTORY_MANAGER', () => {
    render(<RoleBadge role="INVENTORY_MANAGER" />)
    expect(screen.getByText('Inv. Manager')).toBeInTheDocument()
  })

  it('renders Procurement label for PROCUREMENT_ANALYST', () => {
    render(<RoleBadge role="PROCUREMENT_ANALYST" />)
    expect(screen.getByText('Procurement')).toBeInTheDocument()
  })

  it('falls back to the raw role string for unknown roles', () => {
    render(<RoleBadge role="UNKNOWN_ROLE" />)
    expect(screen.getByText('UNKNOWN_ROLE')).toBeInTheDocument()
  })
})
