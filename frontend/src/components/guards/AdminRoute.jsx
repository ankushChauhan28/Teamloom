import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { Spinner } from '../ui/Spinner';

export function AdminRoute({ children }) {
  const { user, isAuthenticated, isLoading } = useAuthStore();

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

  if (user?.role !== 'ADMIN') {
    return <Navigate to="/dashboard" replace />;
  }

  return children ? children : <Outlet />;
}

export default AdminRoute;
