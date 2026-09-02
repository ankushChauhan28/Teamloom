import React, { useState } from 'react'
import { AlertCircle, CheckCircle2, AlertTriangle, Info, X } from 'lucide-react'

const ALERT_CONFIG = {
  error: {
    icon: AlertCircle,
    style: {
      backgroundColor: 'var(--red-bg)',
      color: 'var(--red)',
      borderColor: 'rgba(217, 105, 90, 0.25)',
    },
  },
  danger: {
    icon: AlertCircle,
    style: {
      backgroundColor: 'var(--red-bg)',
      color: 'var(--red)',
      borderColor: 'rgba(217, 105, 90, 0.25)',
    },
  },
  success: {
    icon: CheckCircle2,
    style: {
      backgroundColor: 'var(--green-bg)',
      color: 'var(--green)',
      borderColor: 'rgba(111, 190, 122, 0.25)',
    },
  },
  warning: {
    icon: AlertTriangle,
    style: {
      backgroundColor: 'var(--amber-bg)',
      color: 'var(--amber)',
      borderColor: 'rgba(217, 164, 65, 0.25)',
    },
  },
  info: {
    icon: Info,
    style: {
      backgroundColor: 'var(--teal-bg)',
      color: 'var(--teal)',
      borderColor: 'rgba(63, 168, 143, 0.25)',
    },
  },
}

export function Alert({
  variant = 'info',
  children,
  onDismiss,
  dismissible = true,
  className = '',
}) {
  const [dismissed, setDismissed] = useState(false)
  const config = ALERT_CONFIG[variant] || ALERT_CONFIG.info
  const Icon = config.icon

  if (dismissed) return null

  const handleDismiss = () => {
    setDismissed(true)
    if (onDismiss) onDismiss()
  }

  return (
    <div
      className={`flex items-start gap-2.5 p-3 text-xs rounded-lg border transition-all duration-150 ease-out ${className}`}
      style={config.style}
      role="alert"
    >
      <Icon className="w-4 h-4 shrink-0 mt-0.5" />
      <div className="flex-1 leading-relaxed">{children}</div>
      {dismissible && (
        <button
          onClick={handleDismiss}
          type="button"
          className="shrink-0 p-0.5 opacity-70 hover:opacity-100 transition-opacity cursor-pointer ml-auto"
          aria-label="dismiss alert"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}

export default Alert
