import { type InputHTMLAttributes, type ReactNode } from 'react'

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  label?: string
  error?: string
  helpText?: string
  onChange?: (value: string) => void
  prefix?: ReactNode
  suffix?: ReactNode
}

export function Input({ label, error, helpText, onChange, prefix, suffix, className = '', id, ...rest }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-text-secondary">
          {label}
          {rest.required && <span className="text-danger-400 ml-0.5">*</span>}
        </label>
      )}
      <div className="relative flex items-center">
        {prefix && (
          <div className="absolute left-3 text-text-muted pointer-events-none">{prefix}</div>
        )}
        <input
          {...rest}
          id={inputId}
          onChange={(e) => onChange?.(e.target.value)}
          className={`
            w-full bg-surface-800 border rounded-xl px-4 py-2.5 text-sm text-text-primary
            placeholder:text-text-disabled min-h-touch
            transition-colors duration-150
            ${error
              ? 'border-danger-500 focus:border-danger-400 focus:ring-danger-500/30'
              : 'border-surface-600 focus:border-primary-500 focus:ring-primary-500/20'
            }
            focus:outline-none focus:ring-2
            disabled:opacity-50 disabled:cursor-not-allowed
            ${prefix ? 'pl-10' : ''}
            ${suffix ? 'pr-10' : ''}
          `.trim()}
        />
        {suffix && (
          <div className="absolute right-3 text-text-muted">{suffix}</div>
        )}
      </div>
      {error && <p className="text-danger-400 text-xs">{error}</p>}
      {helpText && !error && <p className="text-text-muted text-xs">{helpText}</p>}
    </div>
  )
}
