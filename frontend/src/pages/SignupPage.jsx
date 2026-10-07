import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { api } from '../lib/api';
import { AuthLayout } from '../components/layout/AuthLayout';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { MailCheck } from 'lucide-react';

export function SignupPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();

  const [companyName, setCompanyName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Success state ("Check your email")
  const [isSignedUp, setIsSignedUp] = useState(false);
  const [signupMessage, setSignupMessage] = useState('');
  const [isResending, setIsResending] = useState(false);
  const [resendAlert, setResendAlert] = useState(null);

  // If already authenticated, redirect based on user role and must_change_password state
  useEffect(() => {
    if (isAuthenticated && user) {
      if (user.must_change_password) {
        navigate('/change-password', { replace: true });
      } else {
        const targetPath = user.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
        navigate(targetPath, { replace: true });
      }
    }
  }, [isAuthenticated, user, navigate]);

  const validate = () => {
    const newErrors = {};

    if (!companyName.trim()) {
      newErrors.companyName = 'Company name is required.';
    }

    if (!fullName.trim()) {
      newErrors.fullName = 'Full name is required.';
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!emailRegex.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters.';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password.';
    } else if (password && confirmPassword !== password) {
      newErrors.confirmPassword = 'Passwords do not match.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    setResendAlert(null);

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const payload = {
        company_name: companyName.trim(),
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
      };

      const res = await api.post('/auth/signup', payload);
      setIsSignedUp(true);
      setSignupMessage(
        res.data?.message ||
          'Signup successful. Please check your email to verify your account.'
      );
    } catch (err) {
      if (err.response?.status === 429) {
        setServerError(
          err.response?.data?.detail ||
            'Too many signup attempts. Please try again later.'
        );
      } else if (err.response?.status === 422) {
        const detail = err.response?.data?.detail;
        if (Array.isArray(detail)) {
          const fieldErrors = {};
          detail.forEach((item) => {
            const field = item.loc?.[item.loc.length - 1];
            if (field === 'company_name') fieldErrors.companyName = item.msg;
            else if (field === 'full_name') fieldErrors.fullName = item.msg;
            else if (field === 'email') fieldErrors.email = item.msg;
            else if (field === 'password') fieldErrors.password = item.msg;
          });
          setErrors((prev) => ({ ...prev, ...fieldErrors }));
          setServerError('Please fix the errors below.');
        } else if (typeof detail === 'string') {
          setServerError(detail);
        } else {
          setServerError('Validation failed. Please check your inputs.');
        }
      } else {
        setServerError('Server error. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendVerification = async () => {
    const targetEmail = email.trim().toLowerCase();
    if (!targetEmail) return;

    setIsResending(true);
    setResendAlert(null);
    try {
      const res = await api.post('/auth/resend-verification', {
        email: targetEmail,
      });
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

  // Check your email state after successful 201 signup
  if (isSignedUp) {
    return (
      <AuthLayout
        title="Check your email"
        subtitle="We've sent a verification link to activate your account."
        headerIcon={MailCheck}
        footer={
          <p className="text-xs text-[var(--text-secondary)]">
            Ready to log in?{' '}
            <Link
              to="/login"
              className="text-[var(--accent)] hover:underline font-medium"
            >
              Back to login
            </Link>
          </p>
        }
      >
        <div className="space-y-4">
          <Alert variant="info" dismissible={false}>
            {signupMessage}
          </Alert>

          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Click the verification link sent to{' '}
            <strong className="text-[var(--text-primary)]">{email.trim()}</strong>{' '}
            to complete your registration. If you do not see it within a few minutes,
            check your spam folder.
          </p>

          <div className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-xs space-y-2">
            <p className="text-[var(--text-muted)]">Didn't receive the email?</p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleResendVerification}
              disabled={isResending}
              className="w-full justify-center"
            >
              {isResending ? (
                <span className="flex items-center gap-1.5">
                  <Spinner size="sm" /> Resending...
                </span>
              ) : (
                'Resend verification email'
              )}
            </Button>
            {resendAlert && (
              <Alert variant={resendAlert.variant} className="mt-2">
                {resendAlert.message}
              </Alert>
            )}
          </div>

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

  const footer = (
    <p className="text-xs text-[var(--text-secondary)]">
      Already have an account?{' '}
      <Link to="/login" className="text-[var(--accent)] hover:underline font-medium">
        Sign in
      </Link>
    </p>
  );

  return (
    <AuthLayout
      title="Create your organization"
      subtitle="Sign up as an admin to manage employees, tasks, and leaves."
      footer={footer}
    >
      {serverError && (
        <Alert variant="danger" className="mb-4">
          {serverError}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Input
          label="Company Name"
          type="text"
          placeholder="Acme Corp"
          value={companyName}
          onChange={(e) => {
            setCompanyName(e.target.value);
            if (errors.companyName) setErrors({ ...errors, companyName: '' });
          }}
          error={errors.companyName}
          disabled={isSubmitting}
          autoComplete="organization"
        />

        <Input
          label="Full Name"
          type="text"
          placeholder="Jane Doe"
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            if (errors.fullName) setErrors({ ...errors, fullName: '' });
          }}
          error={errors.fullName}
          disabled={isSubmitting}
          autoComplete="name"
        />

        <Input
          label="Work Email"
          type="email"
          placeholder="jane@acmecorp.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (errors.email) setErrors({ ...errors, email: '' });
          }}
          error={errors.email}
          disabled={isSubmitting}
          autoComplete="email"
        />

        <Input
          label="Password"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (errors.password) setErrors({ ...errors, password: '' });
          }}
          error={errors.password}
          helperText="Minimum 6 characters required."
          disabled={isSubmitting}
          autoComplete="new-password"
        />

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
        />

        <Button
          type="submit"
          variant="primary"
          className="w-full justify-center mt-2"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <Spinner size="sm" /> Creating account...
            </span>
          ) : (
            'Create Account'
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default SignupPage;
