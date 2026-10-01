import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, getPerformanceAnalytics } from '../lib/api';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { Alert } from '../components/ui/Alert';
import { PerformanceRing } from '../components/PerformanceRing';
import { MilestoneTrail } from '../components/MilestoneTrail';
import { Activity, RefreshCw, Filter, ArrowLeft, Users } from 'lucide-react';

export function AdminPerformancePage() {
  const [stats, setStats] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Fetch all active employees for drill-down filter
  const fetchEmployees = useCallback(async () => {
    try {
      const res = await api.get('/users/');
      const activeUsers = (res.data || []).filter((u) => u.is_active !== false);
      setEmployees(activeUsers);
    } catch (err) {
      console.error('Failed to load employee list:', err);
    }
  }, []);

  // Fetch performance metrics (org-wide or per-employee)
  const fetchAnalytics = useCallback(async (empId = null) => {
    setIsLoading(true);
    setError('');
    try {
      const params = empId && empId !== 'ALL' ? { employee_id: Number(empId) } : {};
      const data = await getPerformanceAnalytics(params);
      setStats(data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load performance analytics. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  useEffect(() => {
    fetchAnalytics(selectedEmployeeId);
  }, [selectedEmployeeId, fetchAnalytics]);

  const selectedEmployee = useMemo(() => {
    if (selectedEmployeeId === 'ALL') return null;
    return employees.find((emp) => String(emp.id) === String(selectedEmployeeId)) || null;
  }, [employees, selectedEmployeeId]);

  const employeeOptions = useMemo(() => [
    { value: 'ALL', label: 'Organization-Wide (All Employees)' },
    ...employees.map((emp) => ({
      value: String(emp.id),
      label: `${emp.full_name} (${emp.employee_code || emp.email})${emp.designation ? ` — ${emp.designation}` : ''}`,
    })),
  ], [employees]);

  const handleRefresh = () => {
    fetchEmployees();
    fetchAnalytics(selectedEmployeeId);
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Top Navbar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-[var(--accent)]" />
              <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                Performance Analytics
              </h1>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Organization-wide completion rates, task distribution metrics, and individual employee performance tracking
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              className="text-xs text-[var(--text-muted)]"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
            </Button>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium mr-1">
              <Filter className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span>Scope Filter:</span>
            </div>

            <Select
              value={selectedEmployeeId}
              onChange={(e) => setSelectedEmployeeId(e.target.value)}
              className="py-1 px-2.5 text-xs h-8 min-w-[260px] max-w-md"
              options={employeeOptions}
            />

            {selectedEmployee && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedEmployeeId('ALL')}
                className="text-xs h-8"
              >
                <ArrowLeft className="w-3 h-3 mr-1" /> Reset to Org-Wide
              </Button>
            )}
          </div>

          <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] font-medium">
            <Users className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>
              {selectedEmployee
                ? `Drill-down: ${selectedEmployee.full_name}`
                : `Organization Aggregate (${employees.length} active employees)`}
            </span>
          </div>
        </div>

        {/* Global Error Banner */}
        {error && <Alert variant="danger">{error}</Alert>}

        {/* Performance Content Card */}
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
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 w-full">
                <div>
                  <CardTitle className="text-base font-semibold">
                    {selectedEmployee
                      ? `Individual Performance: ${selectedEmployee.full_name}`
                      : 'Organization-Wide Performance'}
                  </CardTitle>
                  <CardDescription>
                    {selectedEmployee
                      ? `Analytics for employee code ${selectedEmployee.employee_code || selectedEmployee.email}`
                      : 'Combined performance metrics across all tasks in the system'}
                  </CardDescription>
                </div>

                {selectedEmployee && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setSelectedEmployeeId('ALL')}
                    className="text-xs self-start sm:self-auto"
                  >
                    <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Org-Wide
                  </Button>
                )}
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

export default AdminPerformancePage;
