import React from 'react'
import { Inbox } from 'lucide-react'

export function EmptyState({
  icon: Icon = Inbox,
  title = 'no items found',
  description = 'there are no records to display at this time.',
  action,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center rounded-xl bg-[var(--surface-1)] border border-[var(--border)] ${className}`}
    >
      <div className="p-3 rounded-full bg-[var(--surface-2)] text-[var(--text-muted)] mb-3">
        <Icon className="w-6 h-6 stroke-[1.5]" />
      </div>
      <h3 className="text-sm font-medium text-[var(--text-primary)]">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-[var(--text-secondary)] max-w-sm mt-1">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export default EmptyState
