import React, { useEffect } from 'react'
import { X } from 'lucide-react'

export function Modal({
  isOpen = false,
  onClose,
  title,
  children,
  footer,
  className = '',
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && onClose) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ease-out">
      {/* Backdrop click */}
      <div
        className="fixed inset-0"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div
        className={`relative z-10 w-full max-w-md bg-[var(--surface-2)] border border-[var(--border-strong)] rounded-xl p-5 transition-all duration-150 ease-out max-h-[90vh] flex flex-col ${className}`}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-[var(--border)] shrink-0">
          {title && (
            <h2 className="text-sm font-medium text-[var(--text-primary)]">
              {title}
            </h2>
          )}
          {onClose && (
            <button
              onClick={onClose}
              type="button"
              className="p-1 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-1)] transition-all duration-150 ease-out cursor-pointer ml-auto"
              aria-label="close modal"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="text-sm text-[var(--text-secondary)] overflow-y-auto flex-1 pr-1">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2.5 pt-4 mt-4 border-t border-[var(--border)] shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

export default Modal
