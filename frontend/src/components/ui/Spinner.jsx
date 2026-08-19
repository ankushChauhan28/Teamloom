import React from 'react'

export function Spinner({ size = 'md', className = '' }) {
  const sizeClasses = {
    sm: 'w-3.5 h-3.5 border-2',
    md: 'w-5 h-5 border-2',
    lg: 'w-8 h-8 border-3',
  }

  return (
    <div
      className={`inline-block rounded-full border-[var(--border)] border-t-[var(--accent)] animate-spin ${sizeClasses[size] || sizeClasses.md} ${className}`}
      role="status"
      aria-label="loading"
    />
  )
}

export default Spinner
