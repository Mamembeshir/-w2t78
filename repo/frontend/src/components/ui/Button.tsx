import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import { LoadingSpinner } from './LoadingSpinner'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

const variants: Record<Variant, string> = {
  primary:   'bg-primary-500 hover:bg-primary-600 active:bg-primary-700 text-white shadow-sm disabled:bg-primary-500/50',
  secondary: 'bg-surface-700 hover:bg-surface-600 active:bg-surface-500 text-text-primary border border-surface-600 disabled:opacity-50',
  danger:    'bg-danger-500 hover:bg-danger-600 active:bg-danger-600 text-white shadow-sm disabled:bg-danger-500/50',
  ghost:     'text-text-secondary hover:text-text-primary hover:bg-surface-700 active:bg-surface-600 disabled:opacity-40',
}

const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm min-h-touch rounded-lg',
  md: 'px-4 py-2 text-sm min-h-touch rounded-xl',
  lg: 'px-6 py-3 text-base min-h-touch-lg rounded-xl',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  children,
  className = '',
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center gap-2 font-medium
        transition-colors duration-150 cursor-pointer
        disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-900
        ${variants[variant]} ${sizes[size]} ${className}
      `.trim()}
    >
      {loading && <LoadingSpinner size="sm" />}
      {children}
    </button>
  )
}
