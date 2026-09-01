import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../lib/api';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert } from '../components/ui/Alert';
import { EmployeeFormModal } from '../components/employees/EmployeeFormModal';
import { Plus, Users, RefreshCw, Search, ShieldCheck } from 'lucide-react';

export function AdminEmployeesPage() {
  const [employees, setEmployees] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Notification Banner State (e.g. on new employee creation)
  const [notification, setNotification] = useState(null);

  const fetchEmployees = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const res = await api.get('/users/');
      setEmployees(res.data);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to load employee directory. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  // Employee Map: ID -> Employee Object (for resolving reports_to_id)
  const employeeMap = useMemo(() => {
    const map = {};
    employees.forEach((emp) => {
      map[emp.id] = emp;
    });
    return map;
  }, [employees]);

  // Filtered employees list based on search query
  const filteredEmployees = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return employees;

    return employees.filter((emp) => {
      const nameMatch = emp.full_name?.toLowerCase().includes(query);
      const emailMatch = emp.email?.toLowerCase().includes(query);
      const codeMatch = emp.employee_code?.toLowerCase().includes(query);
      const desigMatch = emp.designation?.toLowerCase().includes(query);

      // Search matching supervisor name as well
      const supervisor = emp.reports_to_id ? employeeMap[emp.reports_to_id] : null;
      const supervisorMatch = supervisor?.full_name?.toLowerCase().includes(query);

      return nameMatch || emailMatch || codeMatch || desigMatch || supervisorMatch;
    });
  }, [employees, searchQuery, employeeMap]);

  const handleEmployeeCreated = (newEmp) => {
    // Refresh employee directory
    fetchEmployees();

    // Show appropriate success / warning notification
    if (newEmp.email_sent) {
      setNotification({
        variant: 'success',
        message: `Employee created successfully — ${newEmp.employee_code} (${newEmp.full_name}). Welcome email sent.`,
      });
    } else {
      setNotification({
        variant: 'warning',
        message: `Employee created (${newEmp.employee_code}), but welcome email could not be sent. Please check your SMTP configuration.`,
      });
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Top Navbar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                Manage Employees
              </h1>
              <Badge variant="violet" size="sm">
                <ShieldCheck className="w-3 h-3 mr-1" />
                Admin
              </Badge>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              System-wide employee directory for provisioning accounts, assigning designations, and configuring reporting hierarchies
            </p>
          </div>

          <Button
            variant="primary"
            size="md"
            onClick={() => setIsModalOpen(true)}
            className="self-start sm:self-auto"
          >
            <Plus className="w-4 h-4 mr-1.5" /> New Employee
          </Button>
        </div>

        {/* Dynamic Notification Banner */}
        {notification && (
          <Alert
            variant={notification.variant}
            onDismiss={() => setNotification(null)}
            className="shadow-sm"
          >
            {notification.message}
          </Alert>
        )}

        {/* Filter & Search Bar */}
        <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by name, employee code, email, designation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text-primary)] text-xs rounded-lg pl-9 pr-3 py-2 placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-[var(--text-muted)] font-medium">
              Showing {filteredEmployees.length} of {employees.length} employees
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchEmployees}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
            </Button>
          </div>
        </div>

        {/* Content Area */}
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <Spinner size="lg" />
            <span className="text-xs text-[var(--text-muted)] animate-pulse">
              Loading employee directory...
            </span>
          </div>
        ) : error ? (
          <div className="space-y-4">
            <Alert variant="danger">{error}</Alert>
            <div className="flex justify-center">
              <Button variant="secondary" size="sm" onClick={fetchEmployees}>
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry Loading
              </Button>
            </div>
          </div>
        ) : filteredEmployees.length === 0 ? (
          <div className="py-8">
            <EmptyState
              icon={Users}
              title={employees.length === 0 ? 'No employees found' : 'No matching employees'}
              description={
                employees.length === 0
                  ? "No employee accounts have been created in the system yet. Click 'New Employee' to provision the first account."
                  : 'No employees match your search query. Try clearing the search filter.'
              }
              action={
                employees.length === 0 ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setIsModalOpen(true)}
                  >
                    <Plus className="w-3.5 h-3.5 mr-1.5" /> Create First Employee
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setSearchQuery('')}
                  >
                    Clear Search
                  </Button>
                )
              }
            />
          </div>
        ) : (
          /* Employee Directory Table */
          <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[var(--surface-2)] text-[11px] font-medium text-[var(--text-secondary)] uppercase tracking-wider border-b border-[var(--border)]">
                    <th className="py-3 px-4">Employee Code</th>
                    <th className="py-3 px-4">Full Name</th>
                    <th className="py-3 px-4">Email</th>
                    <th className="py-3 px-4">Designation</th>
                    <th className="py-3 px-4">Reports To</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] text-xs">
                  {filteredEmployees.map((emp) => {
                    const supervisor = emp.reports_to_id
                      ? employeeMap[emp.reports_to_id]
                      : null;

                    return (
                      <tr
                        key={emp.id}
                        className="hover:bg-[var(--surface-2)]/60 transition-colors"
                      >
                        {/* Employee Code */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[var(--surface-2)] text-[var(--accent)] border border-[var(--border)]">
                            {emp.employee_code || '—'}
                          </span>
                        </td>

                        {/* Full Name */}
                        <td className="py-3 px-4 whitespace-nowrap font-medium text-[var(--text-primary)]">
                          {emp.full_name}
                        </td>

                        {/* Email */}
                        <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px] text-[var(--text-secondary)]">
                          {emp.email}
                        </td>

                        {/* Designation */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {emp.designation ? (
                            <span className="text-xs text-[var(--text-primary)]">
                              {emp.designation}
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)] font-mono">
                              —
                            </span>
                          )}
                        </td>

                        {/* Reports To */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {supervisor ? (
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs text-[var(--text-primary)] font-medium">
                                {supervisor.full_name}
                              </span>
                              <span className="text-[10px] text-[var(--text-muted)] font-mono">
                                ({supervisor.employee_code || supervisor.email})
                              </span>
                            </div>
                          ) : emp.reports_to_id ? (
                            <span className="text-[var(--text-muted)] italic">
                              User #{emp.reports_to_id}
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)] font-mono">
                              —
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Employee Creation Modal */}
      <EmployeeFormModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleEmployeeCreated}
        existingEmployees={employees}
      />
    </div>
  );
}

export default AdminEmployeesPage;
