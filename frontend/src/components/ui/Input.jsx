import React, { useState, useId } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export function Input({
  label,
  error,
  helperText,
  className = '',
  id: customId,
  type = 'text',
  ...props
}) {
  const generatedId = useId();
  const id = customId || generatedId;
  const [showPassword, setShowPassword] = useState(false);

  const isPasswordType = type === 'password';
  const effectiveType = isPasswordType ? (showPassword ? 'text' : 'password') : type;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
          {label}
        </label>
      )}
      <div className="relative w-full">
        <input
          id={id}
          type={effectiveType}
          className={`w-full h-9 px-3 ${isPasswordType ? 'pr-9' : ''} text-sm rounded-lg bg-[var(--surface-1)] text-[var(--text-primary)] placeholder-[var(--text-muted)] border transition-all duration-150 ease-out focus:outline-none ${
            error
              ? 'border-[var(--red)] focus:ring-2 focus:ring-[var(--red)]/30 focus:border-[var(--red)]'
              : 'border-[var(--border)] hover:border-[var(--border-strong)] focus:ring-2 focus:ring-[var(--accent)]/30 focus:border-[var(--accent)]'
          } ${className}`}
          {...props}
        />
        {isPasswordType && (
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-0.5 rounded focus:outline-none focus:ring-1 focus:ring-[var(--accent)] select-none"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            title={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? (
              <Eye className="w-4 h-4" />
            ) : (
              <EyeOff className="w-4 h-4" />
            )}
          </button>
        )}
      </div>
      {error ? (
        <p className="text-xs text-[var(--red)] mt-1">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-[var(--text-muted)] mt-1">{helperText}</p>
      ) : null}
    </div>
  );
}

export default Input;
