import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { AuthLayout } from '../components/layout/AuthLayout';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { CheckCircle2, AlertCircle } from 'lucide-react';

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error'
  const [message, setMessage] = useState('');

  // Resend verification state for failed verification
  const [resendEmail, setResendEmail] = useState('');
  const [resendError, setResendError] = useState('');
  const [isResending, setIsResending] = useState(false);
  const [resendAlert, setResendAlert] = useState(null);

  // Single-use token guard against React StrictMode double effect execution
  const hasRequestedRef = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid or expired verification token.');
      return;
    }

    if (hasRequestedRef.current) return;
    hasRequestedRef.current = true;

    const verifyToken = async () => {
      try {
        const res = await api.post('/auth/verify-email', { token });
        setStatus('success');
        setMessage(res.data?.message || 'Email successfully verified.');
      } catch (err) {
        setStatus('error');
        setMessage(
          err.response?.data?.detail || 'Invalid or expired verification token.'
        );
      }
    };

    verifyToken();
  }, [token]);

  const handleResend = async (e) => {
    e?.preventDefault();
    setResendError('');
    setResendAlert(null);

    const email = resendEmail.trim().toLowerCase();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      setResendError('Please enter a valid email address.');
      return;
    }

    setIsResending(true);
    try {
      const res = await api.post('/auth/resend-verification', { email });
      setResendAlert({
        variant: 'info',
        message:
          res.data?.message ||
          'If an unverified account exists for this email, a verification link has been sent.',
      });
    } catch (err) {
      if (err.response?.status === 429) {
        setResendAlert({
          variant: 'danger',
          message:
            err.response?.data?.detail ||
            'Too many verification requests. Please try again later.',
        });
      } else {
        setResendAlert({
          variant: 'danger',
          message: 'Server error. Please try again.',
        });
      }
    } finally {
      setIsResending(false);
    }
  };

  const footer = (
    <p className="text-xs text-[var(--text-secondary)]">
      Need to sign in?{' '}
      <Link to="/login" className="text-[var(--accent)] hover:underline font-medium">
        Go to login
      </Link>
    </p>
  );

  if (status === 'loading') {
    return (
      <AuthLayout
        title="Verifying your email"
        subtitle="Please wait while we activate your account..."
        footer={footer}
      >
        <div className="py-8 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <span className="text-xs text-[var(--text-muted)] animate-pulse">
            Validating verification token...
          </span>
        </div>
      </AuthLayout>
    );
  }

  if (status === 'success') {
    return (
      <AuthLayout
        title="Email Verified"
        subtitle="Your account is active and ready to use."
        headerIcon={CheckCircle2}
        footer={footer}
      >
        <div className="space-y-4">
          <Alert variant="success" dismissible={false}>
            {message}
          </Alert>

          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Thank you for verifying your email. You can now sign in with your admin
            credentials.
          </p>

          <Button
            type="button"
            variant="primary"
            onClick={() => navigate('/login')}
            className="w-full justify-center mt-2"
          >
            Go to login
          </Button>
        </div>
      </AuthLayout>
    );
  }

  // Error state
  return (
    <AuthLayout
      title="Verification Failed"
      subtitle="We could not verify your email address."
      headerIcon={AlertCircle}
      footer={footer}
    >
      <div className="space-y-4">
        <Alert variant="danger" dismissible={false}>
          {message}
        </Alert>

        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          The link may be invalid, already used, or expired. Request a new
          verification link below to continue.
        </p>

        <form onSubmit={handleResend} className="space-y-3 pt-2" noValidate>
          <Input
            label="Email Address"
            type="email"
            placeholder="admin@example.com"
            value={resendEmail}
            onChange={(e) => {
              setResendEmail(e.target.value);
              if (resendError) setResendError('');
            }}
            error={resendError}
            disabled={isResending}
            autoComplete="email"
          />

          <Button
            type="submit"
            variant="secondary"
            className="w-full justify-center"
            disabled={isResending}
          >
            {isResending ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Resending Link...
              </span>
            ) : (
              'Resend verification email'
            )}
          </Button>
        </form>

        {resendAlert && (
          <Alert variant={resendAlert.variant} className="mt-2">
            {resendAlert.message}
          </Alert>
        )}
      </div>
    </AuthLayout>
  );
}

export default VerifyEmailPage;
