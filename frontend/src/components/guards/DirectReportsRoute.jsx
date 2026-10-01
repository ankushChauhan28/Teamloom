import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { Spinner } from '../ui/Spinner';

export function DirectReportsRoute({ children }) {
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

  // Allow only non-admin users with active direct reports
  const hasDirectReports = user?.role !== 'ADMIN' && (directReports || []).length > 0;

  if (!hasDirectReports) {
    return <Navigate to="/dashboard" replace />;
  }

  return children ? children : <Outlet />;
}

export default DirectReportsRoute;
