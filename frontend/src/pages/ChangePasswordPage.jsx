import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';
import { ShieldAlert, KeyRound, LogOut, ArrowLeft } from 'lucide-react';

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const { changePassword, logout, user } = useAuthStore();

  // Capture flow type once on mount to prevent layout/content flash when user state updates
  const [isForcedFlow] = useState(() => Boolean(user?.must_change_password));

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = () => {
    const newErrors = {};

    if (!currentPassword) {
      newErrors.currentPassword = isForcedFlow
        ? 'Current temporary password is required.'
        : 'Current password is required.';
    }

    if (!newPassword) {
      newErrors.newPassword = 'New password is required.';
    } else if (newPassword.length < 6) {
      newErrors.newPassword = 'New password must be at least 6 characters.';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your new password.';
    } else if (newPassword && confirmPassword !== newPassword) {
      newErrors.confirmPassword = 'Passwords do not match.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleCancel = () => {
    const targetPath = user?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
    navigate(targetPath);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    setSuccessMessage('');

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const updatedUser = await changePassword(currentPassword, newPassword);
      setSuccessMessage('Password changed successfully.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      const targetPath = updatedUser?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard';
      setTimeout(() => {
        navigate(targetPath, { replace: true });
      }, 1200);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to update password. Please check your current password.';
      setServerError(msg);
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const isFormDisabled = isSubmitting || Boolean(successMessage);

  return (
    <div className="min-h-screen bg-[var(--bg-page)] flex flex-col items-center justify-center p-4">
      {/* Brand Header */}
      <div className="flex items-center gap-2 mb-6 select-none">
        <div className="w-9 h-9 rounded-xl bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center text-[var(--accent)]">
          {isForcedFlow ? (
            <ShieldAlert className="w-5 h-5" />
          ) : (
            <KeyRound className="w-5 h-5" />
          )}
        </div>
        <span className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
          Teamloom
        </span>
      </div>

      {/* Change Password Card */}
      <Card className="w-full max-w-md p-6">
        <div className="mb-6">
          {!isForcedFlow && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={isFormDisabled}
              className="inline-flex items-center gap-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors mb-3 cursor-pointer disabled:opacity-50"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back</span>
            </button>
          )}

          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
            {isForcedFlow ? 'Change Temporary Password' : 'Change Password'}
          </h1>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {isForcedFlow
              ? 'As a security requirement, you must update your temporary password before accessing your account dashboard.'
              : 'Enter your current password and choose a new password for your account.'}
          </p>
        </div>

        {serverError && (
          <Alert variant="danger" className="mb-4">
            {serverError}
          </Alert>
        )}

        {successMessage && (
          <Alert variant="success" className="mb-4" dismissible={false}>
            {successMessage}
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Input
            label={isForcedFlow ? 'Current (Temporary) Password' : 'Current Password'}
            type="password"
            placeholder="••••••••••••"
            value={currentPassword}
            onChange={(e) => {
              setCurrentPassword(e.target.value);
              if (errors.currentPassword) setErrors({ ...errors, currentPassword: '' });
            }}
            error={errors.currentPassword}
            disabled={isFormDisabled}
            autoComplete="current-password"
          />

          <Input
            label="New Password"
            type="password"
            placeholder="Minimum 6 characters"
            value={newPassword}
            onChange={(e) => {
              setNewPassword(e.target.value);
              if (errors.newPassword) setErrors({ ...errors, newPassword: '' });
            }}
            error={errors.newPassword}
            disabled={isFormDisabled}
            autoComplete="new-password"
          />

          <Input
            label="Confirm New Password"
            type="password"
            placeholder="Re-enter new password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (errors.confirmPassword) setErrors({ ...errors, confirmPassword: '' });
            }}
            error={errors.confirmPassword}
            disabled={isFormDisabled}
            autoComplete="new-password"
          />

          <div className="flex items-center gap-3 pt-2">
            {!isForcedFlow && (
              <Button
                type="button"
                variant="ghost"
                onClick={handleCancel}
                disabled={isFormDisabled}
                className="flex-1 justify-center"
              >
                Cancel
              </Button>
            )}

            <Button
              type="submit"
              variant="primary"
              className={`${isForcedFlow ? 'w-full' : 'flex-1'} justify-center`}
              disabled={isFormDisabled}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <Spinner size="sm" /> Updating Password...
                </span>
              ) : isForcedFlow ? (
                'Update Password & Continue'
              ) : (
                'Update Password'
              )}
            </Button>
          </div>
        </form>

        {isForcedFlow && (
          <div className="mt-6 pt-4 border-t border-[var(--border)] flex justify-between items-center text-xs text-[var(--text-muted)]">
            <span>Need help? Contact your Admin</span>
            <button
              type="button"
              onClick={handleLogout}
              disabled={isFormDisabled}
              className="flex items-center gap-1 text-[var(--text-secondary)] hover:text-[var(--danger)] transition-colors font-medium cursor-pointer disabled:opacity-50"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign out
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}

export default ChangePasswordPage;
