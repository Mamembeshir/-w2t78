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
  // Amber gold — subtle gradient for depth, dark text for contrast on the bright amber
  primary: [
    'bg-primary-500 hover:bg-primary-600 active:bg-primary-700',
    'text-surface-950 font-semibold',
    'shadow-sm hover:shadow-glow-primary',
    'disabled:bg-primary-500/40 disabled:text-surface-950/60',
  ].join(' '),

  secondary: [
    'bg-surface-700/80 hover:bg-surface-700 active:bg-surface-600',
    'text-text-primary border border-surface-600/80 hover:border-surface-500',
    'disabled:opacity-40',
  ].join(' '),

  danger: [
    'bg-danger-500 hover:bg-danger-600 active:bg-danger-700',
    'text-white shadow-sm hover:shadow-glow-danger',
    'disabled:bg-danger-500/40',
  ].join(' '),

  ghost: [
    'text-text-secondary hover:text-text-primary',
    'hover:bg-primary-500/8 active:bg-primary-500/12',
    'disabled:opacity-40',
  ].join(' '),
}

const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm min-h-touch rounded-xl',
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
        transition-all duration-150 cursor-pointer
        disabled:cursor-not-allowed
        focus-visible:ring-2 focus-visible:ring-primary-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-900
        ${variants[variant]} ${sizes[size]} ${className}
      `.trim()}
    >
      {loading && <LoadingSpinner size="sm" />}
      {children}
    </button>
  )
}
