import React from 'react';
import { useAuthStore } from '../store/authStore';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { TaskList } from '../components/TaskList';
import { ShieldCheck, UserCheck } from 'lucide-react';

export function DashboardPage() {
  const { user } = useAuthStore();

  const roleVariant = user?.role === 'ADMIN' ? 'violet' : 'blue';

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Top Navbar with Profile Bar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Session Active Notice Banner */}
        <Alert variant="success">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--success)] shrink-0" />
            <span>
              Session active &amp; verified. Refresh token is secured via <strong>httpOnly</strong> cookie.
            </span>
          </div>
        </Alert>

        {/* Welcome Hero Panel */}
        <Card className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5 mb-1">
                <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                  Welcome back, {user?.full_name}!
                </h1>
                <Badge variant={roleVariant}>{user?.role}</Badge>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                Logged in as <span className="font-mono text-[var(--text-primary)]">{user?.email}</span>
              </p>
            </div>

            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] bg-[var(--surface-2)] px-3 py-1.5 rounded-lg border border-[var(--border)] self-start sm:self-auto">
              <UserCheck className="w-4 h-4 text-[var(--accent)]" />
              <span>User ID: #{user?.id}</span>
            </div>
          </div>
        </Card>

        {/* Main Employee Task List Board */}
        <TaskList />
      </main>
    </div>
  );
}

export default DashboardPage;
