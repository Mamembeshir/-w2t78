interface LoadingSpinnerProps {
  fullPage?: boolean
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

const sizeMap = { sm: 'w-5 h-5', md: 'w-8 h-8', lg: 'w-12 h-12' }

export function LoadingSpinner({ fullPage = false, size = 'md', label }: LoadingSpinnerProps) {
  const spinner = (
    <div className="flex flex-col items-center gap-3">
      <svg
        className={`${sizeMap[size]} animate-spin text-primary-500`}
        fill="none"
        viewBox="0 0 24 24"
        aria-label={label ?? 'Loading'}
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {label && <p className="text-text-muted text-sm">{label}</p>}
    </div>
  )

  if (fullPage) {
    return (
      <div className="min-h-screen bg-surface-900 flex items-center justify-center">
        {spinner}
      </div>
    )
  }

  return spinner
}
