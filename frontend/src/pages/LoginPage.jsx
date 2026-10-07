import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { api } from '../lib/api';
import { AuthLayout } from '../components/layout/AuthLayout';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, user, isAuthenticated } = useAuthStore();

  const [mode, setMode] = useState('admin');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Unverified admin resend verification state
  const [showAdminResendHelper, setShowAdminResendHelper] = useState(false);
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

  const handleModeChange = (newMode) => {
    if (newMode !== mode) {
      setMode(newMode);
      setIdentifier('');
      setPassword('');
      setErrors({});
      setServerError('');
      setShowAdminResendHelper(false);
      setResendAlert(null);
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!identifier.trim()) {
      newErrors.identifier = mode === 'admin' ? 'Email is required.' : 'User ID is required.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    setShowAdminResendHelper(false);
    setResendAlert(null);

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const userData = await login(identifier.trim(), password, mode);
      if (userData?.must_change_password) {
        navigate('/change-password', { replace: true });
      } else {
        const targetPath = userData?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
        navigate(targetPath, { replace: true });
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setServerError('Incorrect credentials.');
        if (mode === 'admin') {
          setShowAdminResendHelper(true);
        }
      } else if (err.response?.status === 429) {
        setServerError(
          err.response?.data?.detail || 'Too many login attempts. Please try again later.'
        );
      } else {
        setServerError('Server error. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendVerification = async () => {
    const email = identifier.trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      setErrors((prev) => ({
        ...prev,
        identifier: 'Please enter a valid email address to resend verification.',
      }));
      return;
    }

    setIsResending(true);
    setResendAlert(null);
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
      New to Teamloom?{' '}
      <Link to="/signup" className="text-[var(--accent)] hover:underline font-medium">
        Create an account
      </Link>
    </p>
  );

  return (
    <AuthLayout
      title="Login to your account"
      subtitle="Enter your credentials to access your dashboard"
      footer={footer}
    >
      {/* Mode Toggle */}
      <div
        className="flex rounded-lg bg-[var(--surface-2)] p-1 mb-5 border border-[var(--border-subtle)]"
        role="tablist"
        aria-label="Login Mode"
      >
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'admin'}
          onClick={() => handleModeChange('admin')}
          disabled={isSubmitting}
          className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all duration-150 cursor-pointer ${
            mode === 'admin'
              ? 'bg-[var(--surface-1)] text-[var(--text-primary)] shadow-sm border border-[var(--border-strong)]'
              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-transparent'
          }`}
        >
          Login as Admin
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'employee'}
          onClick={() => handleModeChange('employee')}
          disabled={isSubmitting}
          className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all duration-150 cursor-pointer ${
            mode === 'employee'
              ? 'bg-[var(--surface-1)] text-[var(--text-primary)] shadow-sm border border-[var(--border-strong)]'
              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-transparent'
          }`}
        >
          Login as Employee
        </button>
      </div>

      {serverError && (
        <Alert variant="danger" className="mb-4">
          {serverError}
        </Alert>
      )}

      {/* Admin Mode 401 Unverified Helper */}
      {mode === 'admin' && showAdminResendHelper && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-xs space-y-2">
          <p className="text-[var(--text-secondary)]">
            Just signed up? You need to verify your email first.
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleResendVerification}
            disabled={isResending || isSubmitting}
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
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {mode === 'admin' ? (
          <Input
            key="admin-email"
            label="Email"
            type="email"
            placeholder="admin@example.com"
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              if (errors.identifier) setErrors({ ...errors, identifier: '' });
            }}
            error={errors.identifier}
            disabled={isSubmitting}
            autoComplete="username"
          />
        ) : (
          <Input
            key="employee-user-id"
            label="User ID"
            type="text"
            inputMode="numeric"
            placeholder="1000000001"
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              if (errors.identifier) setErrors({ ...errors, identifier: '' });
            }}
            error={errors.identifier}
            disabled={isSubmitting}
            autoComplete="username"
          />
        )}

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
          disabled={isSubmitting}
          autoComplete="current-password"
        />

        <Button
          type="submit"
          variant="primary"
          className="w-full justify-center mt-2"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <Spinner size="sm" /> Logging in...
            </span>
          ) : (
            'Login'
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default LoginPage;
