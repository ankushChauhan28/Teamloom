import React from 'react'

export function Card({
  children,
  className = '',
  hoverable = false,
  onClick,
  ...props
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-[var(--surface-1)] border border-[var(--border)] rounded-xl p-4 transition-all duration-150 ease-out ${
        hoverable || onClick
          ? 'hover:border-[var(--border-strong)] cursor-pointer active:scale-[0.99]'
          : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '' }) {
  return <div className={`mb-3 flex items-center justify-between ${className}`}>{children}</div>
}

export function CardTitle({ children, className = '' }) {
  return <h3 className={`text-sm font-medium text-[var(--text-primary)] ${className}`}>{children}</h3>
}

export function CardDescription({ children, className = '' }) {
  return <p className={`text-xs text-[var(--text-muted)] mt-0.5 ${className}`}>{children}</p>
}

export function CardContent({ children, className = '' }) {
  return <div className={`text-sm text-[var(--text-secondary)] ${className}`}>{children}</div>
}

export function CardFooter({ children, className = '' }) {
  return <div className={`mt-4 pt-3 border-t border-[var(--border)] flex items-center gap-2 ${className}`}>{children}</div>
}

export default Card
