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
        <label htmlFor={selectId} className="text-sm font-medium text-text-secondary">
          {label}
          {required && <span className="text-danger-400 ml-0.5">*</span>}
        </label>
      )}
      <select
        id={selectId}
        value={value}
        disabled={disabled}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className={`
          w-full bg-surface-800 border rounded-xl px-4 py-2.5 text-sm text-text-primary min-h-touch
          transition-colors duration-150 appearance-none cursor-pointer
          ${error
            ? 'border-danger-500 focus:border-danger-400 focus:ring-danger-500/30'
            : 'border-surface-600 focus:border-primary-500 focus:ring-primary-500/20'
          }
          focus:outline-none focus:ring-2
          disabled:opacity-50 disabled:cursor-not-allowed
        `.trim()}
      >
        {placeholder && <option value="" disabled>{placeholder}</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && <p className="text-danger-400 text-xs">{error}</p>}
      {helpText && !error && <p className="text-text-muted text-xs">{helpText}</p>}
    </div>
  )
}
