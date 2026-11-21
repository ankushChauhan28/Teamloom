import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { AuthLayout } from '../components/layout/AuthLayout';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { KeyRound, MailCheck } from 'lucide-react';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const GENERIC_FORGOT_CONFIRMATION =
  'If an account with that email exists, a password reset link has been sent.';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    setError('');

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) {
      setError('Email address is required.');
      return;
    }
    if (!EMAIL_REGEX.test(trimmedEmail)) {
      setError('Please enter a valid email address.');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post('/auth/forgot-password', { email: trimmedEmail });
      setIsSubmitted(true);
    } catch (err) {
      if (err.response?.status === 429) {
        const retryAfter = err.response.headers?.['retry-after'];
        const seconds = parseInt(retryAfter, 10);
        if (!isNaN(seconds) && seconds > 0) {
          const minutes = Math.max(1, Math.ceil(seconds / 60));
          const unit = minutes === 1 ? 'minute' : 'minutes';
          setServerError(`Too many reset attempts. Please try again in about ${minutes} ${unit}.`);
        } else {
          setServerError(
            err.response.data?.detail || 'Too many reset attempts. Please try again later.'
          );
        }
      } else if (!err.response) {
        setServerError('Cannot reach the server. Check your connection or try again shortly.');
      } else {
        // Anti-enumeration: always display generic confirmation even on non-429 unexpected errors
        setIsSubmitted(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const footer = (
    <p className="text-xs text-[var(--text-secondary)]">
      Remember your password?{' '}
      <Link to="/login" className="text-[var(--accent)] hover:underline font-medium">
        Back to login
      </Link>
    </p>
  );

  if (isSubmitted) {
    return (
      <AuthLayout
        title="Check your inbox"
        subtitle="Password reset instructions"
        headerIcon={MailCheck}
        footer={footer}
      >
        <div className="space-y-4">
          <Alert variant="info">{GENERIC_FORGOT_CONFIRMATION}</Alert>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Please check your spam or junk folder if you do not see the email within a few minutes.
          </p>
          <div className="pt-2">
            <Link to="/login" className="block w-full">
              <Button variant="secondary" size="md" className="w-full justify-center">
                Return to Login
              </Button>
            </Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Forgot Password"
      subtitle="Enter your email to receive a password reset link"
      headerIcon={KeyRound}
      footer={footer}
    >
      {serverError && (
        <Alert variant="danger" className="mb-4">
          {serverError}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Input
          label="Account Email"
          type="email"
          placeholder="user@example.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (error) setError('');
          }}
          error={error}
          disabled={isSubmitting}
          autoComplete="email"
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
              <Spinner size="sm" /> Sending reset link...
            </span>
          ) : (
            'Send Password Reset Link'
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default ForgotPasswordPage;
