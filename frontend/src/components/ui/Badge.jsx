import React from 'react'

const VARIANT_MAP = {
  violet: { color: 'var(--violet)', backgroundColor: 'var(--violet-bg)' },
  blue: { color: 'var(--blue)', backgroundColor: 'var(--blue-bg)' },
  amber: { color: 'var(--amber)', backgroundColor: 'var(--amber-bg)' },
  teal: { color: 'var(--teal)', backgroundColor: 'var(--teal-bg)' },
  emerald: { color: 'var(--green)', backgroundColor: 'var(--green-bg)' },
  green: { color: 'var(--green)', backgroundColor: 'var(--green-bg)' },
  coral: { color: 'var(--coral)', backgroundColor: 'var(--coral-bg)' },
  red: { color: 'var(--red)', backgroundColor: 'var(--red-bg)' },
  slate: { color: 'var(--slate)', backgroundColor: 'var(--slate-bg)' },
}

export function Badge({ variant = 'slate', children, className = '' }) {
  const style = VARIANT_MAP[variant] || VARIANT_MAP.slate

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-[11px] font-medium leading-tight select-none ${className}`}
      style={style}
    >
      {children}
    </span>
  )
}

export default Badge
