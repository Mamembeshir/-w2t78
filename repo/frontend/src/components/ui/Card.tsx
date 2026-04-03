import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'sm' | 'md' | 'lg' | 'none'
}

const paddings = { none: '', sm: 'p-4', md: 'p-5', lg: 'p-6' }

export function Card({ children, className = '', padding = 'md' }: CardProps) {
  return (
    <div className={`bg-surface-800 border border-surface-700 rounded-xl shadow-card ${paddings[padding]} ${className}`}>
      {children}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: string | number
  sublabel?: string
  icon?: ReactNode
  accent?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  className?: string
}

const accents = {
  primary: 'text-primary-400 bg-primary-500/10',
  success: 'text-success-400 bg-success-500/10',
  warning: 'text-warning-400 bg-warning-500/10',
  danger:  'text-danger-400 bg-danger-500/10',
  info:    'text-info-400 bg-info-500/10',
}

export function StatCard({ label, value, sublabel, icon, accent = 'primary', className = '' }: StatCardProps) {
  return (
    <Card className={className}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-text-muted text-xs font-medium uppercase tracking-wider truncate">{label}</p>
          <p className="mt-1 text-2xl font-bold text-text-primary tabular-nums">{value}</p>
          {sublabel && <p className="mt-1 text-text-muted text-xs">{sublabel}</p>}
        </div>
        {icon && (
          <div className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${accents[accent]}`}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  )
}
