import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { ProtectedRoute } from './components/guards/ProtectedRoute';
import { AdminRoute } from './components/guards/AdminRoute';
import { ManagerRoute } from './components/guards/ManagerRoute';
import { LoginPage } from './pages/LoginPage';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { AdminTasksPage } from './pages/AdminTasksPage';
import { AdminLeavesPage } from './pages/AdminLeavesPage';
import { LeavesPage } from './pages/LeavesPage';
import { MyTeamPage } from './pages/MyTeamPage';
import { Spinner } from './components/ui/Spinner';

// Component to perform role-based root redirection
function RootRedirect() {
  const { user, isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.must_change_password) return <Navigate to="/change-password" replace />;
  return <Navigate to={user?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard'} replace />;
}

export function App() {
  const { refreshSession, isLoading } = useAuthStore();

  useEffect(() => {
    console.log('[App] App mounted, calling refreshSession()...');
    refreshSession().then((success) => {
      console.log('[App] refreshSession() resolved with result:', success);
    });
  }, [refreshSession]);

  // Full-page Spinner during initial session restoration bootstrap
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--bg-page)] flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-[var(--text-muted)] tracking-tight animate-pulse">
          Authenticating session...
        </span>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Auth Routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Forced Password Change Route */}
        <Route
          path="/change-password"
          element={
            <ProtectedRoute>
              <ChangePasswordPage />
            </ProtectedRoute>
          }
        />

        {/* Employee Dashboard Route */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        {/* Employee & Admin Leave Portal Route */}
        <Route
          path="/leaves"
          element={
            <ProtectedRoute>
              <LeavesPage />
            </ProtectedRoute>
          }
        />

        {/* Manager / Team Lead Portal Route */}
        <Route
          path="/my-team"
          element={
            <ManagerRoute>
              <MyTeamPage />
            </ManagerRoute>
          }
        />

        {/* Admin Task Control Panel Route */}
        <Route
          path="/admin/tasks"
          element={
            <AdminRoute>
              <AdminTasksPage />
            </AdminRoute>
          }
        />

        {/* Admin Leave Approval Hub Route */}
        <Route
          path="/admin/leaves"
          element={
            <AdminRoute>
              <AdminLeavesPage />
            </AdminRoute>
          }
        />

        {/* Default Dynamic Root & Fallback Redirects */}
        <Route path="/" element={<RootRedirect />} />
        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
