import React from 'react';
import { Card } from '../ui/Card';
import { CheckSquare } from 'lucide-react';

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
  headerIcon: HeaderIcon = CheckSquare,
  cardClassName = '',
  className = '',
}) {
  return (
    <div className={`min-h-screen bg-[var(--bg-page)] flex flex-col items-center justify-center p-4 ${className}`}>
      {/* Brand Header */}
      <div className="flex items-center gap-2 mb-6 select-none">
        <div className="w-9 h-9 rounded-xl bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center text-[var(--accent)]">
          <HeaderIcon className="w-5 h-5" />
        </div>
        <span className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
          Teamloom
        </span>
      </div>

      {/* Auth Card */}
      <Card className={`w-full max-w-md p-6 ${cardClassName}`}>
        {(title || subtitle) && (
          <div className="mb-5">
            {title && (
              <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
                {title}
              </h1>
            )}
            {subtitle && (
              <p className="text-xs text-[var(--text-secondary)]">
                {subtitle}
              </p>
            )}
          </div>
        )}

        {children}

        {footer && (
          <div className="mt-6 pt-4 border-t border-[var(--border)] text-center">
            {footer}
          </div>
        )}
      </Card>
    </div>
  );
}

export default AuthLayout;
