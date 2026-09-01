import React, { useState, useEffect, useCallback } from 'react';
import { getPerformanceAnalytics } from '../lib/api';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Spinner } from '../components/ui/Spinner';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { PerformanceRing } from '../components/PerformanceRing';
import { MilestoneTrail } from '../components/MilestoneTrail';
import { Activity, RefreshCw } from 'lucide-react';

export function MyPerformancePage() {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchAnalytics = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await getPerformanceAnalytics();
      setStats(data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load performance analytics. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Navbar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-[var(--accent)]" />
              <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                My Performance Analytics
              </h1>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Personal completion rate, status metrics, and milestone history
            </p>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={fetchAnalytics}
            className="text-xs text-[var(--text-muted)] self-start sm:self-auto"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
          </Button>
        </div>

        {/* Global Error Banner */}
        {error && <Alert variant="danger">{error}</Alert>}

        {/* Content Card */}
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-3">
            <Spinner size="lg" />
            <span className="text-xs text-[var(--text-muted)] animate-pulse">
              Loading performance metrics...
            </span>
          </div>
        ) : stats ? (
          <Card className="space-y-6 p-6">
            <CardHeader className="mb-2">
              <div>
                <CardTitle className="text-base font-semibold">
                  Performance Summary
                </CardTitle>
                <CardDescription>
                  Real-time calculated metrics across assigned tasks
                </CardDescription>
              </div>
            </CardHeader>

            <CardContent className="space-y-8">
              {/* Performance Ring Component */}
              <PerformanceRing stats={stats} />

              {/* Milestone Trail Component */}
              <MilestoneTrail trail={stats.milestone_trail} />
            </CardContent>
          </Card>
        ) : null}
      </main>
    </div>
  );
}

export default MyPerformancePage;
