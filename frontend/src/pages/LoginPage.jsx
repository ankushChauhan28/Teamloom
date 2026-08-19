import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { CheckSquare } from 'lucide-react';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, user, isAuthenticated } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect based on user role
  React.useEffect(() => {
    if (isAuthenticated && user) {
      const targetPath = user.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
      navigate(targetPath, { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  const validate = () => {
    const newErrors = {};
    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters.';
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
      const userData = await login(email.trim(), password);
      const targetPath = userData?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
      navigate(targetPath, { replace: true });
    } catch (err) {
      // Don't distinguish wrong email vs wrong password for security
      const msg =
        err.response?.data?.detail || 'Invalid email or password.';
      setServerError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)] flex flex-col items-center justify-center p-4">
      {/* Brand Header */}
      <div className="flex items-center gap-2 mb-6 select-none">
        <div className="w-9 h-9 rounded-xl bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center text-[var(--accent)]">
          <CheckSquare className="w-5 h-5" />
        </div>
        <span className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
          employee task management
        </span>
      </div>

      {/* Login Card */}
      <Card className="w-full max-w-md p-6">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
            Sign in to your account
          </h1>
          <p className="text-xs text-[var(--text-secondary)]">
            Enter your credentials to access your dashboard
          </p>
        </div>

        {serverError && (
          <Alert variant="danger" className="mb-4">
            {serverError}
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Input
            label="Email address"
            type="email"
            placeholder="you@example.com"
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
                <Spinner size="sm" /> Signing in...
              </span>
            ) : (
              'Sign in'
            )}
          </Button>
        </form>

        <div className="mt-6 pt-4 border-t border-[var(--border)] text-center">
          <p className="text-xs text-[var(--text-secondary)]">
            Don't have an account?{' '}
            <Link
              to="/register"
              className="text-[var(--accent)] hover:underline font-medium"
            >
              Register as Employee
            </Link>
          </p>
        </div>
      </Card>
    </div>
  );
}

export default LoginPage;
