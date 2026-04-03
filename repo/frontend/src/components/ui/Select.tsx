interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectProps {
  label?: string
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  error?: string
  helpText?: string
  placeholder?: string
  disabled?: boolean
  required?: boolean
  className?: string
  id?: string
}

export function Select({ label, options, value, onChange, error, helpText, placeholder, disabled, required, className = '', id }: SelectProps) {
  const selectId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && (
        <label htmlFor={selectId} className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          {label}
          {required && <span className="text-primary-500 ml-0.5">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          value={value}
          disabled={disabled}
          required={required}
          onChange={(e) => onChange(e.target.value)}
          className={`
            w-full bg-surface-900 border rounded-xl px-4 py-3 pr-10 text-sm text-text-primary min-h-touch
            transition-all duration-150 appearance-none cursor-pointer
            ${error
              ? 'border-danger-500/70 focus:border-danger-400 focus:ring-2 focus:ring-danger-500/20'
              : 'border-surface-600/80 hover:border-surface-500 focus:border-primary-500/70 focus:ring-2 focus:ring-primary-500/15'
            }
            focus:outline-none focus:bg-surface-800
            disabled:opacity-40 disabled:cursor-not-allowed
          `.trim()}
        >
          {placeholder && <option value="" disabled>{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled} className="bg-surface-800 text-text-primary">
              {opt.label}
            </option>
          ))}
        </select>
        {/* Custom chevron */}
        <div className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center">
          <svg className="w-4 h-4 text-text-disabled" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 15L12 18.75 15.75 15m-7.5-6L12 5.25 15.75 9" />
          </svg>
        </div>
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
}
