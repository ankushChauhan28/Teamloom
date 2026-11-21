import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { AuthLayout } from '../components/layout/AuthLayout';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { PasswordChecklist } from '../components/ui/PasswordChecklist';
import { isPasswordStrong } from '../lib/passwordUtils';
import { CheckCircle2, KeyRound, AlertCircle } from 'lucide-react';

const GENERIC_RESET_ERROR =
  'This link is invalid or has expired. Please request a new reset link.';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const rawToken = searchParams.get('token');
  const token = rawToken?.trim() || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  // If token is missing from the query string
  if (!token) {
    return (
      <AuthLayout
        title="Invalid Reset Link"
        subtitle="We could not verify your password reset link"
        headerIcon={AlertCircle}
        footer={
          <p className="text-xs text-[var(--text-secondary)]">
            Remember your credentials?{' '}
            <Link to="/login" className="text-[var(--accent)] hover:underline font-medium">
              Log in
            </Link>
          </p>
        }
      >
        <div className="space-y-4">
          <Alert variant="danger">{GENERIC_RESET_ERROR}</Alert>
          <div className="flex flex-col sm:flex-row gap-2 pt-2">
            <Link to="/forgot-password" className="flex-1">
              <Button variant="primary" size="md" className="w-full justify-center">
                Request a new reset link
              </Button>
            </Link>
            <Link to="/login" className="flex-1">
              <Button variant="secondary" size="md" className="w-full justify-center">
                Return to Login
              </Button>
            </Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  // Success State
  if (isSuccess) {
    return (
      <AuthLayout
        title="Password Reset"
        subtitle="Your password has been updated"
        headerIcon={CheckCircle2}
      >
        <div className="space-y-5 text-center">
          <div className="w-12 h-12 rounded-full bg-[var(--green-bg)] text-[var(--green)] flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {successMessage || 'Password has been reset. Please log in.'}
          </p>
          <Link to="/login" className="block w-full">
            <Button variant="primary" size="md" className="w-full justify-center">
              Log in with new password
            </Button>
          </Link>
        </div>
      </AuthLayout>
    );
  }

  const validate = () => {
    const newErrors = {};

    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (!isPasswordStrong(password)) {
      newErrors.password = 'Password does not meet the strength requirements.';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Confirm your new password.';
    } else if (password && confirmPassword !== password) {
      newErrors.confirmPassword = 'Passwords do not match.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const res = await api.post('/auth/reset-password', {
        token,
        new_password: password,
      });

      setIsSuccess(true);
      setSuccessMessage(res.data?.message || 'Password has been reset. Please log in.');
    } catch (err) {
      if (!err.response) {
        setServerError('Cannot reach the server. Check your connection or try again shortly.');
      } else if (err.response.status === 400 || err.response.status === 404) {
        const detail = err.response.data?.detail;
        if (
          typeof detail === 'string' &&
          (detail.toLowerCase().includes('token') ||
            detail.toLowerCase().includes('invalid') ||
            detail.toLowerCase().includes('expired'))
        ) {
          setServerError(GENERIC_RESET_ERROR);
        } else if (typeof detail === 'string') {
          setServerError(detail);
        } else {
          setServerError(GENERIC_RESET_ERROR);
        }
      } else if (err.response.status === 422) {
        console.error('Validation error (422) during reset-password:', err.response.data);
        setServerError('Please check your password and try again.');
      } else if (err.response.status === 429) {
        const retryAfter = err.response.headers?.['retry-after'];
        const seconds = parseInt(retryAfter, 10);
        if (!isNaN(seconds) && seconds > 0) {
          const minutes = Math.max(1, Math.ceil(seconds / 60));
          const unit = minutes === 1 ? 'minute' : 'minutes';
          setServerError(`Too many attempts. Please try again in about ${minutes} ${unit}.`);
        } else {
          setServerError(
            err.response.data?.detail || 'Too many attempts. Please try again later.'
          );
        }
      } else if (err.response.status >= 500) {
        setServerError('Server error. Please try again.');
      } else {
        setServerError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const footer = (
    <p className="text-xs text-[var(--text-secondary)]">
      Need a new link?{' '}
      <Link to="/forgot-password" className="text-[var(--accent)] hover:underline font-medium">
        Request a new reset link
      </Link>
    </p>
  );

  return (
    <AuthLayout
      title="Reset Password"
      subtitle="Choose a new, secure password for your account"
      headerIcon={KeyRound}
      footer={footer}
    >
      {serverError && (
        <Alert variant="danger" className="mb-4">
          <div className="space-y-2">
            <span>{serverError}</span>
            {serverError === GENERIC_RESET_ERROR && (
              <div>
                <Link
                  to="/forgot-password"
                  className="text-xs font-semibold underline hover:no-underline block"
                >
                  Request a new reset link &rarr;
                </Link>
              </div>
            )}
          </div>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <Input
            label="New Password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors({ ...errors, password: '' });
            }}
            error={errors.password}
            disabled={isSubmitting}
            autoComplete="new-password"
            required
          />
          <PasswordChecklist password={password} />
        </div>

        <Input
          label="Confirm New Password"
          type="password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            if (errors.confirmPassword) setErrors({ ...errors, confirmPassword: '' });
          }}
          error={errors.confirmPassword}
          disabled={isSubmitting}
          autoComplete="new-password"
          required
        />

        <Button
          type="submit"
          variant="primary"
          className="w-full justify-center mt-2"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <Spinner size="sm" /> Resetting password...
            </span>
          ) : (
            'Reset Password'
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default ResetPasswordPage;
