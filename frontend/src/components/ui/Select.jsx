import React, { useId } from 'react'
import { ChevronDown } from 'lucide-react'

export function Select({
  label,
  error,
  helperText,
  options = [],
  children,
  className = '',
  id: customId,
  ...props
}) {
  const generatedId = useId()
  const id = customId || generatedId

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={id}
          className={`w-full h-9 pl-3 pr-8 text-sm rounded-lg bg-[var(--surface-1)] text-[var(--text-primary)] border transition-all duration-150 ease-out appearance-none focus:outline-none cursor-pointer ${
            error
              ? 'border-[var(--red)] focus:ring-2 focus:ring-[var(--red)]/30 focus:border-[var(--red)]'
              : 'border-[var(--border)] hover:border-[var(--border-strong)] focus:ring-2 focus:ring-[var(--accent)]/30 focus:border-[var(--accent)]'
          } ${className}`}
          {...props}
        >
          {children ||
            options.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-[var(--surface-2)] text-[var(--text-primary)]">
                {opt.label}
              </option>
            ))}
        </select>
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-[var(--text-secondary)]">
          <ChevronDown className="w-4 h-4" />
        </div>
      </div>
      {error ? (
        <p className="text-xs text-[var(--red)] mt-1">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-[var(--text-muted)] mt-1">{helperText}</p>
      ) : null}
    </div>
  )
}

export default Select
