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
import { CheckCircle2, UserCheck, AlertCircle } from 'lucide-react';

const GENERIC_INVITE_ERROR =
  'This link is invalid or has expired. Ask your admin to resend the invite';

export function AcceptInvitePage() {
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
        title="Invalid Invitation"
        subtitle="We could not verify your invitation link"
        headerIcon={AlertCircle}
        footer={
          <p className="text-xs text-[var(--text-secondary)]">
            Already have an active account?{' '}
            <Link to="/login" className="text-[var(--accent)] hover:underline font-medium">
              Log in
            </Link>
          </p>
        }
      >
        <div className="space-y-4">
          <Alert variant="danger">{GENERIC_INVITE_ERROR}</Alert>
          <div className="flex justify-center pt-2">
            <Link to="/login">
              <Button variant="secondary" size="md">
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
        title="Account Activated"
        subtitle="Your account is ready"
        headerIcon={CheckCircle2}
      >
        <div className="space-y-5 text-center">
          <div className="w-12 h-12 rounded-full bg-[var(--green-bg)] text-[var(--green)] flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {successMessage || 'Account activated. You may now log in.'}
          </p>
          <Link to="/login" className="block w-full">
            <Button variant="primary" size="md" className="w-full justify-center">
              Proceed to Login
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
      newErrors.confirmPassword = 'Confirm your password.';
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
      const res = await api.post('/auth/accept-invite', {
        token,
        password,
      });

      setIsSuccess(true);
      setSuccessMessage(res.data?.message || 'Account activated. You may now log in.');
    } catch (err) {
      if (!err.response) {
        setServerError('Cannot reach the server. Check your connection or try again shortly.');
      } else if (err.response.status === 400) {
        const detail = err.response.data?.detail;
        if (
          typeof detail === 'string' &&
          (detail.toLowerCase().includes('token') ||
            detail.toLowerCase().includes('invalid') ||
            detail.toLowerCase().includes('expired'))
        ) {
          setServerError(GENERIC_INVITE_ERROR);
        } else if (typeof detail === 'string') {
          setServerError(detail);
        } else {
          setServerError(GENERIC_INVITE_ERROR);
        }
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
        setServerError(GENERIC_INVITE_ERROR);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const footer = (
    <p className="text-xs text-[var(--text-secondary)]">
      Already activated?{' '}
      <Link to="/login" className="text-[var(--accent)] hover:underline font-medium">
        Log in to your account
      </Link>
    </p>
  );

  return (
    <AuthLayout
      title="Accept Invitation"
      subtitle="Choose a secure password to activate your account"
      headerIcon={UserCheck}
      footer={footer}
    >
      {serverError && (
        <Alert variant="danger" className="mb-4">
          {serverError}
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
          label="Confirm Password"
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
              <Spinner size="sm" /> Activating account...
            </span>
          ) : (
            'Set Password & Activate Account'
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default AcceptInvitePage;
