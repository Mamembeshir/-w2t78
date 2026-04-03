import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

// Omit 'onChange' (replaced with string-value callback) and 'prefix' (HTML attr is string,
// but we want ReactNode for icon/text prefix decorators).
interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'prefix'> {
  label?: string
  error?: string
  helpText?: string
  onChange?: (value: string) => void
  prefix?: ReactNode
  suffix?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input(
    { label, error, helpText, onChange, prefix, suffix, className = '', id, ...rest },
    ref,
  ) {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className={`flex flex-col gap-1.5 ${className}`}>
        {label && (
          <label htmlFor={inputId} className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            {label}
            {rest.required && <span className="text-primary-500 ml-0.5">*</span>}
          </label>
        )}
        <div className="relative flex items-center">
          {prefix && (
            <div className="absolute left-3.5 text-text-disabled pointer-events-none flex items-center">{prefix}</div>
          )}
          <input
            {...rest}
            ref={ref}
            id={inputId}
            onChange={(e) => onChange?.(e.target.value)}
            className={`
              w-full bg-surface-900 border rounded-xl px-4 py-3 text-sm text-text-primary
              placeholder:text-text-disabled min-h-touch
              transition-all duration-150
              ${error
                ? 'border-danger-500/70 focus:border-danger-400 focus:ring-2 focus:ring-danger-500/20'
                : 'border-surface-600/80 hover:border-surface-500 focus:border-primary-500/70 focus:ring-2 focus:ring-primary-500/15'
              }
              focus:outline-none focus:bg-surface-800
              disabled:opacity-40 disabled:cursor-not-allowed
              ${prefix ? 'pl-10' : ''}
              ${suffix ? 'pr-10' : ''}
            `.trim()}
          />
          {suffix && (
            <div className="absolute right-3.5 text-text-disabled flex items-center">{suffix}</div>
          )}
        </div>
        {error && (
          <p className="text-danger-400 text-xs flex items-center gap-1">
            <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            {error}
          </p>
        )}
        {helpText && !error && <p className="text-text-disabled text-xs">{helpText}</p>}
      </div>
    )
  },
)
