import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
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

  const [employeeCode, setEmployeeCode] = useState('');
  const [password, setPassword] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect based on user role and must_change_password state
  React.useEffect(() => {
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
    if (!employeeCode.trim()) {
      newErrors.employeeCode = 'User ID is required.';
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

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const userData = await login(employeeCode.trim(), password);
      if (userData?.must_change_password) {
        navigate('/change-password', { replace: true });
      } else {
        const targetPath = userData?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
        navigate(targetPath, { replace: true });
      }
    } catch (err) {
      const msg =
        err.response?.data?.detail || 'Incorrect employee ID or password.';
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
          Teamloom
        </span>
      </div>

      {/* Login Card */}
      <Card className="w-full max-w-md p-6">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
            Login to your account
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
            label="User ID"
            type="text"
            inputMode="numeric"
            placeholder="1000000001"
            value={employeeCode}
            onChange={(e) => {
              setEmployeeCode(e.target.value);
              if (errors.employeeCode) setErrors({ ...errors, employeeCode: '' });
            }}
            error={errors.employeeCode}
            disabled={isSubmitting}
            autoComplete="username"
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
                <Spinner size="sm" /> Logging in...
              </span>
            ) : (
              'Login'
            )}
          </Button>
        </form>
      </Card>
    </div>
  );
}

export default LoginPage;
