import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, fetchAllEmployees } from '../lib/api';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert } from '../components/ui/Alert';
import { LeaveRejectModal } from '../components/LeaveRejectModal';
import { Check, X, Calendar, RefreshCw, Filter } from 'lucide-react';

const STATUS_MAP = {
  PENDING: { variant: 'amber', label: 'Pending' },
  APPROVED: { variant: 'emerald', label: 'Approved' },
  REJECTED: { variant: 'red', label: 'Rejected' },
};

function calculateDurationDays(startStr, endStr) {
  if (!startStr || !endStr) return 0;
  const [sY, sM, sD] = startStr.split('-').map(Number);
  const [eY, eM, eD] = endStr.split('-').map(Number);
  const start = new Date(sY, sM - 1, sD);
  const end = new Date(eY, eM - 1, eD);
  const diffMs = end.getTime() - start.getTime();
  const days = Math.round(diffMs / (1000 * 60 * 60 * 24)) + 1;
  return days > 0 ? days : 1;
}

export function AdminLeavesPage() {
  const [leaves, setLeaves] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Default status filter to PENDING so pending requests are shown prominently
  const [statusFilter, setStatusFilter] = useState('PENDING');

  // Row-level action loading & error states
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [actionError, setActionError] = useState('');

  // Rejection modal state
  const [rejectingLeave, setRejectingLeave] = useState(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [leavesRes, allEmployees] = await Promise.all([
        api.get('/leaves/?limit=100'),
        fetchAllEmployees(),
      ]);
      setLeaves(leavesRes.data);
      setEmployees(allEmployees);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load leave requests. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Employee Map: ID -> Employee Object
  const employeeMap = useMemo(() => {
    const map = {};
    employees.forEach((emp) => {
      map[emp.id] = emp;
    });
    return map;
  }, [employees]);

  // Filtered Leave List
  const filteredLeaves = useMemo(() => {
    if (statusFilter === 'ALL') return leaves;
    return leaves.filter((leave) => leave.status === statusFilter);
  }, [leaves, statusFilter]);

  // Inline Approve Action
  const handleApprove = async (leaveId) => {
    setActionError('');
    setActionLoadingId(leaveId);
    try {
      const res = await api.patch(`/leaves/${leaveId}`, { status: 'APPROVED' });
      const updatedLeave = res.data;
      setLeaves((prev) => prev.map((l) => (l.id === leaveId ? updatedLeave : l)));
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to approve leave request.';
      setActionError(msg);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Rejection Callback from Modal
  const handleLeaveRejected = (updatedLeave) => {
    setLeaves((prev) => prev.map((l) => (l.id === updatedLeave.id ? updatedLeave : l)));
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Top Navbar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Page Header */}
        <div className="pb-4 border-b border-[var(--border)]">
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">
            Leave Approval Hub
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            System-wide admin management for reviewing, approving, and rejecting employee leave requests
          </p>
        </div>

        {/* Action Error Banner */}
        {actionError && (
          <Alert variant="danger">{actionError}</Alert>
        )}

        {/* Filter Bar */}
        <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium mr-1">
              <Filter className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span>Status Filter:</span>
            </div>

            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="py-1 px-2.5 text-xs h-8 min-w-[150px]"
              options={[
                { value: 'PENDING', label: 'Pending Review' },
                { value: 'ALL', label: 'All Statuses' },
                { value: 'APPROVED', label: 'Approved' },
                { value: 'REJECTED', label: 'Rejected' },
              ]}
            />
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-[var(--text-muted)] font-medium">
              Showing {filteredLeaves.length} of {leaves.length} requests
            </span>
            <Button variant="ghost" size="sm" onClick={fetchData} className="text-xs text-[var(--text-muted)]">
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
            </Button>
          </div>
        </div>

        {/* Content Area */}
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-3">
            <Spinner size="lg" />
            <span className="text-xs text-[var(--text-muted)] animate-pulse">
              Loading leave requests...
            </span>
          </div>
        ) : error ? (
          <div className="space-y-4">
            <Alert variant="danger">{error}</Alert>
            <div className="flex justify-center">
              <Button variant="secondary" size="sm" onClick={fetchData}>
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry Loading
              </Button>
            </div>
          </div>
        ) : filteredLeaves.length === 0 ? (
          <div className="py-8">
            <EmptyState
              icon={Calendar}
              title="No leave requests found"
              description={
                statusFilter === 'PENDING'
                  ? "There are currently no pending leave requests requiring review."
                  : "No leave requests match your selected status filter criteria."
              }
              action={
                statusFilter !== 'ALL' ? (
                  <Button variant="secondary" size="sm" onClick={() => setStatusFilter('ALL')}>
                    Show All Leave Requests
                  </Button>
                ) : null
              }
            />
          </div>
        ) : (
          /* System-Wide Leave Table */
          <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[var(--surface-2)] text-[11px] font-medium text-[var(--text-secondary)] uppercase tracking-wider border-b border-[var(--border)]">
                    <th className="py-3 px-4">Employee</th>
                    <th className="py-3 px-4">Date Range</th>
                    <th className="py-3 px-4">Reason</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Submitted On</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] text-xs">
                  {filteredLeaves.map((leave) => {
                    const employee = employeeMap[leave.employee_id];
                    const statusInfo = STATUS_MAP[leave.status] || { variant: 'slate', label: leave.status };
                    const duration = calculateDurationDays(leave.start_date, leave.end_date);
                    const submittedAt = new Date(leave.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    });

                    const isPending = leave.status === 'PENDING';
                    const isRowActionLoading = actionLoadingId === leave.id;

                    return (
                      <tr
                        key={leave.id}
                        className="hover:bg-[var(--surface-2)]/60 transition-colors"
                      >
                        {/* Employee Name & Email */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {employee ? (
                            <div className="flex flex-col">
                              <span className="font-medium text-[var(--text-primary)]">
                                {employee.full_name}
                              </span>
                              <span className="text-[10px] text-[var(--text-muted)] font-mono">
                                {employee.email}
                              </span>
                            </div>
                          ) : (
                            <span className="text-[var(--text-muted)] italic">
                              Employee #{leave.employee_id}
                            </span>
                          )}
                        </td>

                        {/* Date Range & Duration */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <div className="flex flex-col">
                            <span className="font-medium text-[var(--text-primary)]">
                              {leave.start_date} <span className="text-[var(--text-muted)]">→</span> {leave.end_date}
                            </span>
                            <span className="text-[10px] text-[var(--text-secondary)]">
                              {duration} {duration === 1 ? 'day' : 'days'}
                            </span>
                          </div>
                        </td>

                        {/* Reason */}
                        <td className="py-3 px-4 max-w-xs sm:max-w-md">
                          <div className="text-[var(--text-secondary)] leading-relaxed">
                            {leave.reason}
                          </div>
                        </td>

                        {/* Status Badge */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <Badge variant={statusInfo.variant} size="sm">
                            {statusInfo.label}
                          </Badge>
                        </td>

                        {/* Submitted On Timestamp */}
                        <td className="py-3 px-4 whitespace-nowrap text-[var(--text-muted)]">
                          {submittedAt}
                        </td>

                        {/* Actions (Approve / Reject) */}
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          {isPending ? (
                            <div className="flex items-center justify-end gap-1.5">
                              {isRowActionLoading ? (
                                <div className="flex items-center gap-1 text-[var(--accent)] text-[11px] px-2 py-1">
                                  <Spinner size="sm" />
                                  <span>Saving...</span>
                                </div>
                              ) : (
                                <>
                                  <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => handleApprove(leave.id)}
                                    className="px-2.5 py-1 text-xs text-[var(--green)] hover:text-[var(--green)] hover:bg-[var(--green-bg)] border-[var(--border)]"
                                    title="Approve Leave"
                                  >
                                    <Check className="w-3.5 h-3.5 mr-1" /> Approve
                                  </Button>
                                  <Button
                                    variant="danger"
                                    size="sm"
                                    onClick={() => setRejectingLeave(leave)}
                                    className="px-2.5 py-1 text-xs"
                                    title="Reject Leave"
                                  >
                                    <X className="w-3.5 h-3.5 mr-1" /> Reject
                                  </Button>
                                </>
                              )}
                            </div>
                          ) : (
                            <span className="text-[11px] text-[var(--text-muted)] italic">
                              Reviewed
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

      {/* Leave Rejection Confirmation Modal */}
      <LeaveRejectModal
        isOpen={Boolean(rejectingLeave)}
        onClose={() => setRejectingLeave(null)}
        onSuccess={handleLeaveRejected}
        leave={rejectingLeave}
        employee={rejectingLeave ? employeeMap[rejectingLeave.employee_id] : null}
      />
    </div>
  );
}

export default AdminLeavesPage;
