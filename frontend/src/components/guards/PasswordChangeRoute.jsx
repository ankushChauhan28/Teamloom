import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { Spinner } from '../ui/Spinner';

export function PasswordChangeRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // 1. If unauthenticated -> redirect to /login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // 2. Authenticated user (forced or voluntary) -> render children
  return children ? children : <Outlet />;
}

export default PasswordChangeRoute;
