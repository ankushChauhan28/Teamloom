import React from 'react';
import { CheckCircle2, Circle } from 'lucide-react';
import { SPECIAL_CHAR_REGEX } from '../../lib/passwordUtils';

export function PasswordChecklist({ password = '' }) {
  const rules = [
    { label: 'At least 8 characters', met: password.length >= 8 },
    { label: 'At least one uppercase letter (A-Z)', met: /[A-Z]/.test(password) },
    { label: 'At least one lowercase letter (a-z)', met: /[a-z]/.test(password) },
    { label: 'At least one number (0-9)', met: /[0-9]/.test(password) },
    {
      label: 'At least one special character (!@#$%^&*...)',
      met: SPECIAL_CHAR_REGEX.test(password),
    },
  ];

  return (
    <div className="mt-2 p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-xs space-y-1.5">
      <span className="font-medium text-[var(--text-secondary)] block mb-1">
        Password requirements:
      </span>
      {rules.map((rule, idx) => (
        <div key={idx} className="flex items-center gap-2">
          {rule.met ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-[var(--green)] shrink-0" />
          ) : (
            <Circle className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
          )}
          <span
            className={
              rule.met
                ? 'text-[var(--text-primary)] font-medium'
                : 'text-[var(--text-muted)]'
            }
          >
            {rule.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default PasswordChecklist;
