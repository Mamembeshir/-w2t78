import type { ReactNode } from 'react'

interface PageWrapperProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}

export function PageWrapper({ title, subtitle, actions, children }: PageWrapperProps) {
  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 pb-1">
        <div>
          <h1 className="text-xl font-bold text-text-primary tracking-tight">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-text-muted">{subtitle}</p>}
          {/* Amber underline accent */}
          <div className="mt-3 w-8 h-0.5 rounded-full bg-primary-500/60" />
        </div>
        {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
      </div>
      {/* Page content */}
      {children}
    </div>
  )
}
