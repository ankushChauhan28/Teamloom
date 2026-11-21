import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { api, fetchAllEmployees } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert } from '../components/ui/Alert';
import { Modal } from '../components/ui/Modal';
import { Select } from '../components/ui/Select';
import { EmployeeFormModal } from '../components/employees/EmployeeFormModal';
import {
  Plus,
  Users,
  RefreshCw,
  Search,
  ShieldCheck,
  UserCheck,
  UserX,
  RotateCcw,
  AlertTriangle,
  Send,
  KeyRound,
  XCircle,
} from 'lucide-react';

function formatApiError(err, fallback = 'Operation failed.') {
  if (!err.response) {
    return 'Cannot reach the server. Check your connection or try again shortly.';
  }
  const { status, data, headers } = err.response;
  if (status === 429) {
    const retryAfter = headers?.['retry-after'];
    const seconds = parseInt(retryAfter, 10);
    if (!isNaN(seconds) && seconds > 0) {
      const minutes = Math.max(1, Math.ceil(seconds / 60));
      const unit = minutes === 1 ? 'minute' : 'minutes';
      return `Rate limit exceeded. Please try again in about ${minutes} ${unit}.`;
    }
    return data?.detail || 'Too many requests. Please try again later.';
  }
  if (status === 404) {
    return data?.detail || 'Employee not found.';
  }
  if (status === 400) {
    return data?.detail || 'Invalid request.';
  }
  return data?.detail || fallback;
}

/* Custom hook to log state changes */
function useLoggedState(initialValue, stateName) {
  const [state, setState] = useState(initialValue);
  const prevRef = useRef(initialValue);

  const setLoggedState = useCallback((newValue) => {
    const resolvedValue = typeof newValue === 'function' ? newValue(prevRef.current) : newValue;
    console.log(`[State Change: ${stateName}] Old: "${prevRef.current}" -> New: "${resolvedValue}"`);
    prevRef.current = resolvedValue;
    setState(resolvedValue);
  }, [stateName]);

  return [state, setLoggedState];
}

/* Modal to change an employee's supervisor (reports_to_id) */
function SupervisorChangeModal({ isOpen, onClose, onSuccess, employee, employees }) {
  const [selectedSupervisorId, setSelectedSupervisorId] = useState(
    employee?.reports_to_id ? String(employee.reports_to_id) : ''
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useLoggedState('', `SupervisorModal(${employee?.id}).serverError`);

  if (!isOpen || !employee) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    setIsSubmitting(true);

    try {
      const payload = {
        reports_to_id: selectedSupervisorId ? Number(selectedSupervisorId) : null,
      };
      console.log(`[SupervisorModal] Submitting PATCH /users/${employee.id}/reports-to with payload:`, payload);
      await api.patch(`/users/${employee.id}/reports-to`, payload);
      onSuccess(`Supervisor updated for ${employee.full_name}.`);
      onClose();
    } catch (err) {
      const msg =
        err.response?.data?.detail || 'Failed to update supervisor. Please try again.';
      console.error(`[SupervisorModal Error] PATCH /users/${employee.id}/reports-to failed:`, msg);
      setServerError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeSupervisorOptions = employees
    .filter(
      (emp) =>
        emp.is_active !== false &&
        emp.id !== employee.id &&
        emp.invitation_status !== 'PENDING' &&
        emp.invitation_status !== 'REVOKED'
    )
    .map((emp) => {
      const codeOrEmail = emp.employee_code || emp.email;
      const desigSuffix = emp.designation ? ` — ${emp.designation}` : '';
      return {
        value: String(emp.id),
        label: `${emp.full_name} (${codeOrEmail})${desigSuffix}`,
      };
    });

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Change Supervisor for ${employee.full_name}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                Updating...
              </span>
            ) : (
              'Save Supervisor'
            )}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {serverError && (
          <Alert variant="danger" className="mb-2">
            {serverError}
          </Alert>
        )}

        <div className="text-xs text-[var(--text-secondary)] mb-2">
          Select a supervisor for <span className="font-semibold text-[var(--text-primary)]">{employee.full_name}</span> ({employee.employee_code || employee.email}).
        </div>

        <Select
          label="New Supervisor"
          value={selectedSupervisorId}
          onChange={(e) => {
            setSelectedSupervisorId(e.target.value);
            if (serverError) setServerError('');
          }}
          disabled={isSubmitting}
          options={[
            { value: '', label: 'None (Top Level / No Supervisor)' },
            ...activeSupervisorOptions,
          ]}
        />
      </form>
    </Modal>
  );
}

/* Modal to confirm employee removal & reassign direct reports if conflict arises */
function RemoveConfirmModal({ isOpen, onClose, onConfirm, employee, allEmployees = [] }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useLoggedState('', `RemoveModal(${employee?.id}).serverError`);
  const [unresolvedSubordinates, setUnresolvedSubordinates] = useState(null);
  const [reassignments, setReassignments] = useState({});

  useEffect(() => {
    console.log(`[RemoveModal Mounted] employee.id: ${employee?.id}, employee.name: "${employee?.full_name}", isOpen: ${isOpen}`);
    setUnresolvedSubordinates(null);
    setReassignments({});
    setServerError('');
  }, [employee, isOpen, setServerError]);

  if (!isOpen || !employee) return null;

  const availableManagers = (allEmployees || []).filter(
    (u) =>
      u.is_active &&
      u.id !== employee.id &&
      u.invitation_status !== 'PENDING' &&
      u.invitation_status !== 'REVOKED'
  );

  const handleSubordinateChange = (subId, managerId) => {
    setReassignments((prev) => ({
      ...prev,
      [subId]: managerId,
    }));
  };

  const handleRemove = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setIsSubmitting(true);
    setServerError('');

    try {
      if (unresolvedSubordinates && unresolvedSubordinates.length > 0) {
        // Reassignment step
        const mapping = {};
        unresolvedSubordinates.forEach((sub) => {
          const val = reassignments[sub.id];
          mapping[sub.id] = (val && val !== '') ? Number(val) : null;
        });
        await onConfirm(employee, { reassignments: mapping });
      } else {
        // Initial deactivation attempt
        await onConfirm(employee);
      }
      onClose();
    } catch (err) {
      if (err.response?.status === 409) {
        const subs = err.response?.data?.unresolved_subordinates || err.response?.data?.subordinates || [];
        if (subs.length > 0) {
          setUnresolvedSubordinates(subs);
          const initialMap = {};
          subs.forEach((s) => {
            initialMap[s.id] = '';
          });
          setReassignments(initialMap);
          setServerError('');
          return;
        }
      }
      const msg = err.response?.data?.detail || 'Failed to remove employee.';
      console.error(`[RemoveModal Error] Removal failed for User #${employee.id}:`, msg);
      setServerError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isReassignmentMode = Boolean(unresolvedSubordinates && unresolvedSubordinates.length > 0);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isReassignmentMode ? 'Reassign Direct Reports' : 'Remove Employee'}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleRemove} disabled={isSubmitting}>
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                {isReassignmentMode ? 'Reassigning...' : 'Removing...'}
              </span>
            ) : isReassignmentMode ? (
              'Reassign & Remove Employee'
            ) : (
              'Remove Employee'
            )}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {serverError && <Alert variant="danger">{serverError}</Alert>}

        {isReassignmentMode ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-[var(--yellow)]/10 border border-[var(--yellow)]/20 text-xs text-[var(--yellow)]">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-[var(--yellow)]" />
              <div>
                <p className="font-semibold text-sm mb-1 text-[var(--text-primary)]">
                  Subordinates Require Reassignment
                </p>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  <span className="font-semibold text-[var(--text-primary)]">{employee.full_name}</span> currently supervises {unresolvedSubordinates.length} active employee(s).
                  Select a new supervisor for each person, or choose &quot;No manager&quot;.
                </p>
              </div>
            </div>

            <div className="max-h-60 overflow-y-auto space-y-3 pr-1">
              {unresolvedSubordinates.map((sub) => {
                const subOptions = [
                  { value: '', label: '-- No manager (unassigned) --' },
                  ...availableManagers
                    .filter((u) => u.id !== sub.id)
                    .map((u) => ({
                      value: String(u.id),
                      label: `${u.full_name}${u.designation ? ` (${u.designation})` : ''}`,
                    })),
                ];

                return (
                  <div
                    key={sub.id}
                    className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-xs text-[var(--text-primary)]">
                        {sub.full_name}
                      </span>
                      {sub.designation && (
                        <span className="text-[10px] text-[var(--text-muted)]">
                          {sub.designation}
                        </span>
                      )}
                    </div>
                    <Select
                      label="New Supervisor"
                      options={subOptions}
                      value={reassignments[sub.id] ?? ''}
                      onChange={(e) => handleSubordinateChange(sub.id, e.target.value)}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3 p-3 rounded-lg bg-[var(--red)]/10 border border-[var(--red)]/20 text-xs text-[var(--red)]">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-sm mb-1">Confirm Employee Removal</p>
              <p className="text-[11px] opacity-90 leading-relaxed">
                Are you sure you want to remove <span className="font-bold">{employee.full_name}</span> ({employee.employee_code || employee.email})?
                This will immediately revoke their ability to log in. If this employee has active direct reports, you will be prompted to reassign them. Historical tasks and leave records will remain untouched.
              </p>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

export function AdminEmployeesPage() {
  const { user: currentUser } = useAuthStore();
  const [employees, setEmployees] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showRemoved, setShowRemoved] = useState(false);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [supervisorModalTarget, setSupervisorModalTarget] = useState(null);
  const [removeModalTarget, setRemoveModalTarget] = useState(null);

  // Notification Banner State
  const [notification, setNotification] = useLoggedState(null, 'AdminEmployeesPage.notification');

  const fetchEmployees = useCallback(async () => {
    console.log('[AdminEmployeesPage] Initiating fetchEmployees() -> fetchAllEmployees()');
    setIsLoading(true);
    setError('');
    try {
      const data = await fetchAllEmployees();
      console.log(`[AdminEmployeesPage] fetchEmployees() success -> Loaded ${data?.length} users:`, data.map(u => ({ id: u.id, name: u.full_name, active: u.is_active })));
      setEmployees(data);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to load employee directory. Please try again.';
      console.error('[AdminEmployeesPage] fetchEmployees() error:', msg);
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

  // Active vs Total Counts
  const activeCount = useMemo(() => {
    return employees.filter((emp) => emp.is_active !== false).length;
  }, [employees]);

  const removedCount = useMemo(() => {
    return employees.filter((emp) => emp.is_active === false).length;
  }, [employees]);

  // Filtered employees list based on search query and showRemoved toggle
  const filteredEmployees = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return employees.filter((emp) => {
      // 1. Filter by active status unless showRemoved toggle is enabled
      const isActive = emp.is_active !== false;
      if (!showRemoved && !isActive) return false;

      // 2. Filter by search query if present
      if (!query) return true;

      const nameMatch = emp.full_name?.toLowerCase().includes(query);
      const emailMatch = emp.email?.toLowerCase().includes(query);
      const codeMatch = emp.employee_code?.toLowerCase().includes(query);
      const desigMatch = emp.designation?.toLowerCase().includes(query);

      // Search matching supervisor name as well
      const supervisor = emp.reports_to_id ? employeeMap[emp.reports_to_id] : null;
      const supervisorMatch = supervisor?.full_name?.toLowerCase().includes(query);

      return nameMatch || emailMatch || codeMatch || desigMatch || supervisorMatch;
    });
  }, [employees, searchQuery, showRemoved, employeeMap]);

  const handleOpenCreateModal = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    console.log('[AdminEmployeesPage] User clicked New Employee button');
    setNotification(null);
    setTimeout(() => {
      setIsModalOpen(true);
    }, 0);
  };

  const handleOpenSupervisorModal = (e, emp) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    console.log(`[AdminEmployeesPage] User clicked Supervisor button on table row for User #${emp.id} (${emp.full_name})`);
    setNotification(null);
    setTimeout(() => {
      setSupervisorModalTarget(emp);
    }, 0);
  };

  const handleOpenRemoveModal = (e, emp) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    console.log(`[AdminEmployeesPage] User clicked Remove button on table row for User #${emp.id} (${emp.full_name}) -> DEFERRING MODAL OPEN`);
    setNotification(null);
    // Use setTimeout(..., 0) to ensure the table row click finishes completely before mounting the modal into DOM
    setTimeout(() => {
      console.log(`[AdminEmployeesPage] Setting removeModalTarget to User #${emp.id}`);
      setRemoveModalTarget(emp);
    }, 0);
  };

  const handleEmployeeCreated = (newEmp) => {
    console.log('[AdminEmployeesPage] handleEmployeeCreated received new employee:', newEmp);
    fetchEmployees();
    setNotification({
      variant: 'success',
      message: `Employee created — ${newEmp.employee_code} (${newEmp.full_name}). Invite sent (queued).`,
    });
  };

  const handleResendInvite = async (e, emp) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setNotification(null);
    try {
      const res = await api.post(`/users/${emp.id}/resend-invite`);
      setNotification({
        variant: 'success',
        message: `${res.data?.message || 'Invitation resent.'} (queued)`,
      });
    } catch (err) {
      setNotification({
        variant: 'danger',
        message: formatApiError(err, 'Failed to resend invite.'),
      });
    }
  };

  const handleRevokeInvite = async (e, emp) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setNotification(null);
    try {
      const res = await api.post(`/users/${emp.id}/revoke-invite`);
      setNotification({
        variant: 'info',
        message: res.data?.message || 'Invitation revoked.',
      });
      fetchEmployees();
    } catch (err) {
      setNotification({
        variant: 'danger',
        message: formatApiError(err, 'Failed to revoke invite.'),
      });
    }
  };

  const handleSendPasswordReset = async (e, emp) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setNotification(null);
    try {
      const res = await api.post(`/users/${emp.id}/send-password-reset`);
      setNotification({
        variant: 'success',
        message: `${res.data?.message || 'Password reset link sent.'} (queued)`,
      });
    } catch (err) {
      setNotification({
        variant: 'danger',
        message: formatApiError(err, 'Failed to send password reset link.'),
      });
    }
  };

  const handleRemoveConfirm = async (employee, reassignmentData = null) => {
    console.log(`[AdminEmployeesPage] Executing PATCH /users/${employee.id}/deactivate`);
    try {
      await api.patch(`/users/${employee.id}/deactivate`, reassignmentData || undefined);
      console.log(`[AdminEmployeesPage] Deactivate request completed for User #${employee.id}`);
      fetchEmployees();
      setNotification({
        variant: 'info',
        message: `Employee ${employee.full_name} (${employee.employee_code || employee.email}) has been removed.`,
      });
    } catch (err) {
      if (err.response?.status === 404) {
        console.warn(`[AdminEmployeesPage] User #${employee.id} was not found on server (stale row). Refreshing directory...`);
        fetchEmployees();
      }
      throw err;
    }
  };

  const handleRestore = async (e, employee) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    try {
      console.log(`[AdminEmployeesPage] Executing PATCH /users/${employee.id}/reactivate`);
      setNotification(null);
      await api.patch(`/users/${employee.id}/reactivate`);
      console.log(`[AdminEmployeesPage] Reactivate request completed for User #${employee.id}`);
      fetchEmployees();
      setNotification({
        variant: 'success',
        message: `Employee ${employee.full_name} (${employee.employee_code || employee.email}) has been restored.`,
      });
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to restore employee.';
      console.error(`[AdminEmployeesPage] Reactivate request failed for User #${employee.id}:`, msg);
      if (err.response?.status === 404) {
        fetchEmployees();
      }
      setNotification({ variant: 'danger', message: msg });
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
              System-wide employee directory for provisioning accounts, assigning designations, removing former staff, and configuring reporting hierarchies
            </p>
          </div>

          <Button
            variant="primary"
            size="md"
            onClick={handleOpenCreateModal}
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

        {/* Filter, Search & Toggle Bar */}
        <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col md:flex-row md:items-center justify-between gap-4">
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

          <div className="flex flex-wrap items-center gap-4">
            {/* Show Removed Employees Toggle Chip */}
            <button
              type="button"
              onClick={() => setShowRemoved(!showRemoved)}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 select-none cursor-pointer border ${
                showRemoved
                  ? 'bg-[var(--surface-2)] text-[var(--accent)] border-[var(--accent)]/40 shadow-xs'
                  : 'bg-transparent text-[var(--text-secondary)] border-[var(--border)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-2)]/50'
              }`}
            >
              <span>Show Removed Employees</span>
              {removedCount > 0 && (
                <span
                  className={`font-mono text-[10px] px-1.5 py-0.5 rounded-full transition-colors ${
                    showRemoved
                      ? 'bg-[var(--accent)]/15 text-[var(--accent)] border border-[var(--accent)]/30 font-semibold'
                      : 'bg-[var(--surface-2)] text-[var(--text-muted)] border border-[var(--border)]'
                  }`}
                >
                  {removedCount}
                </span>
              )}
            </button>

            <div className="h-4 w-px bg-[var(--border)] hidden sm:block" />

            {/* Dynamic Counter & Refresh */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-[var(--text-muted)] font-medium">
                Showing {filteredEmployees.length} of {showRemoved ? employees.length : activeCount} employees
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
                  : searchQuery
                  ? 'No employees match your search query. Try clearing the search filter.'
                  : 'No active employees to display.'
              }
              action={
                employees.length === 0 ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleOpenCreateModal}
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
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] text-xs">
                  {filteredEmployees.map((emp) => {
                    const supervisor = emp.reports_to_id
                      ? employeeMap[emp.reports_to_id]
                      : null;
                    const isActive = emp.is_active !== false;
                    const isSelf = currentUser?.id === emp.id;

                    return (
                      <tr
                        key={emp.id}
                        className={`transition-colors ${
                          isActive
                            ? 'hover:bg-[var(--surface-2)]/60'
                            : 'opacity-60 bg-[var(--surface-2)]/30'
                        }`}
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
                          {isSelf && (
                            <span className="ml-2 text-[10px] text-[var(--text-muted)] font-normal italic">
                              (You)
                            </span>
                          )}
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

                        {/* Status Badge */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {emp.invitation_status === 'PENDING' ? (
                            <Badge variant="amber" size="sm">
                              Invite pending
                            </Badge>
                          ) : emp.invitation_status === 'REVOKED' ? (
                            <Badge variant="slate" size="sm">
                              Revoked
                            </Badge>
                          ) : !isActive ? (
                            <Badge variant="slate" size="sm">
                              Removed
                            </Badge>
                          ) : (
                            <Badge variant="emerald" size="sm">
                              Active
                            </Badge>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-2">
                            {emp.invitation_status === 'PENDING' ? (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleResendInvite(e, emp)}
                                  className="text-xs text-[var(--accent)] hover:text-[var(--accent)]"
                                  title="Resend invitation link"
                                >
                                  <Send className="w-3.5 h-3.5 mr-1" />
                                  Resend invite
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleRevokeInvite(e, emp)}
                                  className="text-xs text-[var(--red)] hover:text-[var(--red)]"
                                  title="Revoke invitation"
                                >
                                  <XCircle className="w-3.5 h-3.5 mr-1 text-[var(--red)]" />
                                  Revoke invite
                                </Button>
                              </>
                            ) : emp.invitation_status === 'REVOKED' ? (
                              <span className="text-[11px] text-[var(--text-muted)] italic">
                                Revoked
                              </span>
                            ) : isActive ? (
                              <>
                                {/* Change Supervisor Button */}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleOpenSupervisorModal(e, emp)}
                                  className="text-xs text-[var(--text-secondary)] hover:text-[var(--accent)]"
                                  title="Change Supervisor"
                                >
                                  <UserCheck className="w-3.5 h-3.5 mr-1" />
                                  Supervisor
                                </Button>

                                {/* Send password reset link */}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleSendPasswordReset(e, emp)}
                                  className="text-xs text-[var(--text-secondary)] hover:text-[var(--accent)]"
                                  title="Send password reset link"
                                >
                                  <KeyRound className="w-3.5 h-3.5 mr-1" />
                                  Send password reset link
                                </Button>

                                {/* Remove Button */}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleOpenRemoveModal(e, emp)}
                                  disabled={isSelf}
                                  className="text-xs text-[var(--text-muted)] hover:text-[var(--red)] disabled:opacity-30 disabled:cursor-not-allowed"
                                  title={isSelf ? 'You cannot remove your own account' : 'Remove Employee'}
                                >
                                  <UserX className="w-3.5 h-3.5 mr-1 text-[var(--red)]" />
                                  Remove
                                </Button>
                              </>
                            ) : (
                              /* Restore Button */
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => handleRestore(e, emp)}
                                className="text-xs text-[var(--teal)] hover:text-[var(--teal)] font-medium"
                                title="Restore Employee"
                              >
                                <RotateCcw className="w-3.5 h-3.5 mr-1 text-[var(--teal)]" />
                                Restore
                              </Button>
                            )}
                          </div>
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
      {isModalOpen && (
        <EmployeeFormModal
          key="create-employee-modal"
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={handleEmployeeCreated}
          existingEmployees={employees}
        />
      )}

      {/* Supervisor Change Modal */}
      {supervisorModalTarget && (
        <SupervisorChangeModal
          key={`supervisor-modal-${supervisorModalTarget.id}`}
          isOpen={Boolean(supervisorModalTarget)}
          onClose={() => setSupervisorModalTarget(null)}
          onSuccess={(msg) => {
            fetchEmployees();
            setNotification({ variant: 'success', message: msg });
          }}
          employee={supervisorModalTarget}
          employees={employees}
        />
      )}

      {/* Remove Confirm Modal */}
      {removeModalTarget && (
        <RemoveConfirmModal
          key={`remove-modal-${removeModalTarget.id}`}
          isOpen={Boolean(removeModalTarget)}
          onClose={() => setRemoveModalTarget(null)}
          onConfirm={handleRemoveConfirm}
          employee={removeModalTarget}
          allEmployees={employees}
        />
      )}
    </div>
  );
}

export default AdminEmployeesPage;
