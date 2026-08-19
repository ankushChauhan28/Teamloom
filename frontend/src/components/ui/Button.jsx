import React from 'react'
import { Spinner } from './Spinner'

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className = '',
  type = 'button',
  onClick,
  ...props
}) {
  const baseClasses =
    'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-150 ease-out cursor-pointer active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none disabled:transform-none select-none'

  const variantClasses = {
    primary:
      'bg-[var(--accent)] text-[var(--on-accent)] hover:bg-[var(--accent-hover)] active:bg-[var(--accent-active)]',
    secondary:
      'bg-transparent border border-[var(--border-strong)] text-[var(--text-primary)] hover:bg-[var(--surface-2)]',
    ghost:
      'bg-transparent text-[var(--text-primary)] hover:bg-[var(--surface-1)]',
    danger:
      'bg-[var(--red)] text-[var(--bg-page)] hover:opacity-90 active:opacity-100',
  }

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs h-8',
    md: 'px-4 py-2 text-sm h-9',
  }

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant] || variantClasses.primary} ${sizeClasses[size] || sizeClasses.md} ${className}`}
      {...props}
    >
      {loading && <Spinner size={size === 'sm' ? 'sm' : 'md'} />}
      <span>{children}</span>
    </button>
  )
}

export default Button
