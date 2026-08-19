import React, { useId } from 'react'

export function Textarea({
  label,
  error,
  helperText,
  className = '',
  id: customId,
  rows = 3,
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
      <textarea
        id={id}
        rows={rows}
        className={`w-full p-2.5 text-sm rounded-lg bg-[var(--surface-1)] text-[var(--text-primary)] placeholder-[var(--text-muted)] border transition-all duration-150 ease-out focus:outline-none ${
          error
            ? 'border-[var(--red)] focus:ring-2 focus:ring-[var(--red)]/30 focus:border-[var(--red)]'
            : 'border-[var(--border)] hover:border-[var(--border-strong)] focus:ring-2 focus:ring-[var(--accent)]/30 focus:border-[var(--accent)]'
        } ${className}`}
        {...props}
      />
      {error ? (
        <p className="text-xs text-[var(--red)] mt-1">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-[var(--text-muted)] mt-1">{helperText}</p>
      ) : null}
    </div>
  )
}

export default Textarea
