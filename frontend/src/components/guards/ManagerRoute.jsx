import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { Spinner } from '../ui/Spinner';

export function ManagerRoute({ children }) {
  const { user, isAuthenticated, isLoading, directReports } = useAuthStore();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user?.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  const hasReports = (directReports || []).length > 0;
  if (!hasReports) {
    return <Navigate to={user?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard'} replace />;
  }

  return children ? children : <Outlet />;
}

export default ManagerRoute;
