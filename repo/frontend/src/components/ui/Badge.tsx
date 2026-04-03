import type { ReactNode } from 'react'

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary'

interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  className?: string
}

const variants: Record<BadgeVariant, string> = {
  success: 'bg-success-500/15 text-success-400 ring-1 ring-success-500/30',
  warning: 'bg-warning-500/15 text-warning-400 ring-1 ring-warning-500/30',
  danger:  'bg-danger-500/15 text-danger-400 ring-1 ring-danger-500/30',
  info:    'bg-info-500/15 text-info-400 ring-1 ring-info-500/30',
  neutral: 'bg-surface-700 text-text-secondary ring-1 ring-surface-600',
  primary: 'bg-primary-500/15 text-primary-400 ring-1 ring-primary-500/30',
}

export function Badge({ variant = 'neutral', children, className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  )
}

export function RoleBadge({ role }: { role: string }) {
  const map: Record<string, { label: string; variant: BadgeVariant }> = {
    ADMIN:                { label: 'Admin', variant: 'danger' },
    INVENTORY_MANAGER:    { label: 'Inv. Manager', variant: 'success' },
    PROCUREMENT_ANALYST:  { label: 'Procurement', variant: 'info' },
  }
  const config = map[role] ?? { label: role, variant: 'neutral' as BadgeVariant }
  return <Badge variant={config.variant}>{config.label}</Badge>
}
