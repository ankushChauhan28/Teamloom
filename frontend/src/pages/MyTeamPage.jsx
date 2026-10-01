import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, getPerformanceAnalytics } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert } from '../components/ui/Alert';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { TaskFormModal } from '../components/TaskFormModal';
import { TaskDeleteModal } from '../components/TaskDeleteModal';
import { DueCountdown } from '../components/ui/DueCountdown';
import { PerformanceRing } from '../components/PerformanceRing';
import { MilestoneTrail } from '../components/MilestoneTrail';
import {
  Users,
  Plus,
  CheckSquare,
  Calendar,
  Filter,
  RefreshCw,
  Edit3,
  Trash2,
  UserCheck,
  Activity,
  ArrowLeft,
} from 'lucide-react';

const PRIORITY_MAP = {
  LOW: { variant: 'slate', label: 'Low' },
  MEDIUM: { variant: 'amber', label: 'Medium' },
  HIGH: { variant: 'coral', label: 'High' },
};

const TASK_STATUS_MAP = {
  PENDING: { variant: 'amber', label: 'Pending' },
  IN_PROGRESS: { variant: 'teal', label: 'In Progress' },
  COMPLETED: { variant: 'emerald', label: 'Completed' },
};

const LEAVE_STATUS_MAP = {
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

export function MyTeamPage() {
  const { directReports: authStoreReports, fetchDirectReports } = useAuthStore();
  const [reports, setReports] = useState((authStoreReports || []).filter((r) => r.is_active !== false));
  const [teamTasks, setTeamTasks] = useState([]);
  const [teamLeaves, setTeamLeaves] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Active View Tab ('tasks' | 'leaves' | 'performance')
  const [activeTab, setActiveTab] = useState('tasks');

  // Task Filter States
  const [taskStatusFilter, setTaskStatusFilter] = useState('ALL');
  const [taskPriorityFilter, setTaskPriorityFilter] = useState('ALL');
  const [taskReportFilter, setTaskReportFilter] = useState('ALL');

  // Leave Filter State
  const [leaveStatusFilter, setLeaveStatusFilter] = useState('ALL');

  // Performance Tab States
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [perfStats, setPerfStats] = useState(null);
  const [isPerfLoading, setIsPerfLoading] = useState(false);
  const [perfError, setPerfError] = useState('');



  // Task Modal States
  const [isTaskFormModalOpen, setIsTaskFormModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [isTaskDeleteModalOpen, setIsTaskDeleteModalOpen] = useState(false);
  const [deletingTask, setDeletingTask] = useState(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [reportsData, tasksRes, leavesRes] = await Promise.all([
        fetchDirectReports(),
        api.get('/tasks/team'),
        api.get('/leaves/team'),
      ]);
      setReports((reportsData || []).filter((r) => r.is_active !== false));
      setTeamTasks(tasksRes.data || []);
      setTeamLeaves(leavesRes.data || []);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load team data. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [fetchDirectReports]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch Performance Analytics (Team aggregate or individual employee)
  const fetchPerformanceData = useCallback(async (empId = null) => {
    setIsPerfLoading(true);
    setPerfError('');
    try {
      const params = empId ? { employee_id: empId } : {};
      const data = await getPerformanceAnalytics(params);
      setPerfStats(data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load team performance analytics.';
      setPerfError(msg);
    } finally {
      setIsPerfLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'performance') {
      fetchPerformanceData(selectedEmployee?.id || null);
    }
  }, [activeTab, selectedEmployee, fetchPerformanceData]);

  // Direct Report Map: ID -> User Object
  const reportMap = useMemo(() => {
    const map = {};
    reports.forEach((r) => {
      map[r.id] = r;
    });
    return map;
  }, [reports]);

  // Filtered Team Tasks
  const filteredTasks = useMemo(() => {
    return teamTasks.filter((task) => {
      if (taskStatusFilter !== 'ALL' && task.status !== taskStatusFilter) return false;
      if (taskPriorityFilter !== 'ALL' && task.priority !== taskPriorityFilter) return false;
      if (taskReportFilter !== 'ALL' && String(task.assigned_to) !== taskReportFilter) return false;
      return true;
    });
  }, [teamTasks, taskStatusFilter, taskPriorityFilter, taskReportFilter]);

  // Filtered Team Leaves
  const filteredLeaves = useMemo(() => {
    if (leaveStatusFilter === 'ALL') return teamLeaves;
    return teamLeaves.filter((l) => l.status === leaveStatusFilter);
  }, [teamLeaves, leaveStatusFilter]);



  const handleTaskDeleted = (deletedTaskId) => {
    setTeamTasks((prev) => prev.filter((t) => t.id !== deletedTaskId));
  };

  const handleOpenCreateTaskModal = () => {
    setEditingTask(null);
    setIsTaskFormModalOpen(true);
  };

  const handleOpenEditTaskModal = (task) => {
    setEditingTask(task);
    setIsTaskFormModalOpen(true);
  };

  const handleOpenDeleteTaskModal = (task) => {
    setDeletingTask(task);
    setIsTaskDeleteModalOpen(true);
  };

  const reportOptions = reports.map((r) => {
    const codeOrEmail = r.employee_code || r.email;
    const desigSuffix = r.designation ? ` — ${r.designation}` : '';
    return {
      value: String(r.id),
      label: `${r.full_name} (${codeOrEmail})${desigSuffix}`,
    };
  });

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
              <Users className="w-5 h-5 text-[var(--accent)]" />
              <h1 className="text-xl font-semibold text-[var(--text-primary)]">
                My Team Management
              </h1>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Direct report roster, team task assignment, leave approvals, and performance analytics
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchData}
              className="text-xs text-[var(--text-muted)]"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
            </Button>
            <Button variant="primary" size="md" onClick={handleOpenCreateTaskModal}>
              <Plus className="w-4 h-4 mr-1.5" /> Assign Team Task
            </Button>
          </div>
        </div>

        {/* Global Error Banner */}
        {error && <Alert variant="danger">{error}</Alert>}

        {/* Direct Reports Roster */}
        <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-xl p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
              <UserCheck className="w-4 h-4 text-[var(--accent)]" />
              <span>Direct Reports ({reports.length})</span>
            </h2>
            {selectedEmployee && (
              <span className="text-xs text-[var(--accent)] font-medium">
                Viewing: {selectedEmployee.full_name}
              </span>
            )}
          </div>

          {reports.length === 0 ? (
            <div className="text-xs text-[var(--text-muted)] italic py-2">
              No direct reports assigned.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {reports.map((report) => {
                const isSelected = selectedEmployee?.id === report.id;
                return (
                  <div
                    key={report.id}
                    onClick={() => {
                      if (activeTab === 'performance') {
                        setSelectedEmployee(isSelected ? null : report);
                      }
                    }}
                    className={`bg-[var(--surface-2)]/60 border rounded-lg p-3 flex items-center gap-3 transition-all ${
                      activeTab === 'performance' ? 'cursor-pointer hover:border-[var(--accent)]' : ''
                    } ${
                      isSelected
                        ? 'border-[var(--accent)] bg-[var(--surface-2)] ring-1 ring-[var(--accent)]'
                        : 'border-[var(--border)]'
                    }`}
                  >
                    <div className="w-9 h-9 rounded-full bg-[var(--accent-bg)] border border-[var(--accent)]/30 text-[var(--accent)] font-semibold flex items-center justify-center text-xs">
                      {report.full_name ? report.full_name.charAt(0).toUpperCase() : 'U'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-medium text-xs text-[var(--text-primary)] truncate">
                          {report.full_name}
                        </span>
                        {report.employee_code && (
                          <span className="text-[10px] font-mono bg-[var(--surface-1)] px-1.5 py-0.5 rounded border border-[var(--border)] text-[var(--accent)]">
                            {report.employee_code}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)] truncate mt-0.5">
                        {report.email}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Navigation Tabs (Team Tasks vs Team Leaves vs Team Performance) */}
        <div className="flex items-center gap-2 border-b border-[var(--border)] pb-1">
          <button
            onClick={() => setActiveTab('tasks')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-t-lg transition-all ${
              activeTab === 'tasks'
                ? 'bg-[var(--surface-1)] text-[var(--accent)] border-t border-x border-[var(--border)] -mb-px font-semibold'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>Team Tasks ({teamTasks.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('leaves')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-t-lg transition-all ${
              activeTab === 'leaves'
                ? 'bg-[var(--surface-1)] text-[var(--accent)] border-t border-x border-[var(--border)] -mb-px font-semibold'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>Team Leave Requests ({teamLeaves.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('performance')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-t-lg transition-all ${
              activeTab === 'performance'
                ? 'bg-[var(--surface-1)] text-[var(--accent)] border-t border-x border-[var(--border)] -mb-px font-semibold'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Performance</span>
          </button>
        </div>

        {/* Tab 1: Team Tasks */}
        {activeTab === 'tasks' && (
          <div className="space-y-4">
            {/* Filter Bar */}
            <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3 flex-1">
                <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium mr-1">
                  <Filter className="w-3.5 h-3.5 text-[var(--accent)]" />
                  <span>Filters:</span>
                </div>

                <Select
                  value={taskStatusFilter}
                  onChange={(e) => setTaskStatusFilter(e.target.value)}
                  className="py-1 px-2.5 text-xs h-8 min-w-[130px]"
                  options={[
                    { value: 'ALL', label: 'All Statuses' },
                    { value: 'PENDING', label: 'Pending' },
                    { value: 'IN_PROGRESS', label: 'In Progress' },
                    { value: 'COMPLETED', label: 'Completed' },
                  ]}
                />

                <Select
                  value={taskPriorityFilter}
                  onChange={(e) => setTaskPriorityFilter(e.target.value)}
                  className="py-1 px-2.5 text-xs h-8 min-w-[130px]"
                  options={[
                    { value: 'ALL', label: 'All Priorities' },
                    { value: 'LOW', label: 'Low' },
                    { value: 'MEDIUM', label: 'Medium' },
                    { value: 'HIGH', label: 'High' },
                  ]}
                />

                <Select
                  value={taskReportFilter}
                  onChange={(e) => setTaskReportFilter(e.target.value)}
                  className="py-1 px-2.5 text-xs h-8 min-w-[160px]"
                  options={[
                    { value: 'ALL', label: 'All Team Members' },
                    ...reportOptions,
                  ]}
                />
              </div>

              <span className="text-xs text-[var(--text-muted)] font-medium">
                Showing {filteredTasks.length} of {teamTasks.length} tasks
              </span>
            </div>

            {/* Content Table / Empty State */}
            {isLoading ? (
              <div className="py-16 flex flex-col items-center justify-center space-y-3">
                <Spinner size="lg" />
                <span className="text-xs text-[var(--text-muted)] animate-pulse">
                  Loading team tasks...
                </span>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="py-8">
                <EmptyState
                  icon={CheckSquare}
                  title="No team tasks found"
                  description={
                    teamTasks.length === 0
                      ? "No tasks have been assigned to your direct reports yet. Click 'Assign Team Task' to assign the first task."
                      : "No team tasks match your selected filter criteria."
                  }
                  action={
                    teamTasks.length === 0 ? (
                      <Button variant="primary" size="sm" onClick={handleOpenCreateTaskModal}>
                        <Plus className="w-3.5 h-3.5 mr-1.5" /> Assign First Task
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setTaskStatusFilter('ALL');
                          setTaskPriorityFilter('ALL');
                          setTaskReportFilter('ALL');
                        }}
                      >
                        Reset Filters
                      </Button>
                    )
                  }
                />
              </div>
            ) : (
              <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-xl overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-[var(--surface-2)] text-[11px] font-medium text-[var(--text-secondary)] uppercase tracking-wider border-b border-[var(--border)]">
                        <th className="py-3 px-4">Task Details</th>
                        <th className="py-3 px-4">Assigned To</th>
                        <th className="py-3 px-4">Priority</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Due Date</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)] text-xs">
                      {filteredTasks.map((task) => {
                        const assignee = reportMap[task.assigned_to];
                        const priorityInfo = PRIORITY_MAP[task.priority] || { variant: 'slate', label: task.priority };
                        const statusInfo = TASK_STATUS_MAP[task.status] || { variant: 'slate', label: task.status };

                        return (
                          <tr
                            key={task.id}
                            className="hover:bg-[var(--surface-2)]/60 transition-colors"
                          >
                            <td className="py-3 px-4 max-w-xs sm:max-w-md">
                              <div className="font-medium text-[var(--text-primary)] text-sm mb-0.5">
                                {task.title}
                              </div>
                              {task.description && (
                                <div className="text-[var(--text-muted)] line-clamp-1 text-[11px]">
                                  {task.description}
                                </div>
                              )}
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              {assignee ? (
                                <div className="flex flex-col">
                                  <span className="font-medium text-[var(--text-primary)]">
                                    {assignee.full_name}
                                  </span>
                                  <span className="text-[10px] text-[var(--text-muted)] font-mono">
                                    {assignee.employee_code || assignee.email}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-[var(--text-muted)] italic">
                                  User #{task.assigned_to}
                                </span>
                              )}
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              <Badge variant={priorityInfo.variant} size="sm">
                                {priorityInfo.label}
                              </Badge>
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              <Badge variant={statusInfo.variant} size="sm">
                                {statusInfo.label}
                              </Badge>
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              <DueCountdown dueDatetime={task.due_datetime || task.due_date} status={task.status} />
                            </td>

                            <td className="py-3 px-4 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleOpenEditTaskModal(task)}
                                  className="p-1.5 h-8 text-[var(--text-secondary)] hover:text-[var(--accent)]"
                                  title="Edit Task"
                                >
                                  <Edit3 className="w-3.5 h-3.5" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleOpenDeleteTaskModal(task)}
                                  className="p-1.5 h-8 text-[var(--text-secondary)] hover:text-[var(--red)]"
                                  title="Delete Task"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </Button>
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
          </div>
        )}

        {/* Tab 2: Team Leave Requests (Read-only view for direct reports) */}
        {activeTab === 'leaves' && (
          <div className="space-y-4">
            {/* Filter Bar */}
            <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3 flex-1">
                <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium mr-1">
                  <Filter className="w-3.5 h-3.5 text-[var(--accent)]" />
                  <span>Status Filter:</span>
                </div>

                <Select
                  value={leaveStatusFilter}
                  onChange={(e) => setLeaveStatusFilter(e.target.value)}
                  className="py-1 px-2.5 text-xs h-8 min-w-[150px]"
                  options={[
                    { value: 'ALL', label: 'All Statuses' },
                    { value: 'PENDING', label: 'Pending Review' },
                    { value: 'APPROVED', label: 'Approved' },
                    { value: 'REJECTED', label: 'Rejected' },
                  ]}
                />
              </div>

              <div className="flex flex-col sm:items-end gap-0.5">
                <span className="text-xs text-[var(--text-muted)] font-medium">
                  Showing {filteredLeaves.length} of {teamLeaves.length} requests
                </span>
                <span className="text-[11px] text-[var(--text-muted)] italic">
                  Approvals handled by Tier 1 Admin only
                </span>
              </div>
            </div>

            {/* Content Table / Empty State */}
            {isLoading ? (
              <div className="py-16 flex flex-col items-center justify-center space-y-3">
                <Spinner size="lg" />
                <span className="text-xs text-[var(--text-muted)] animate-pulse">
                  Loading team leave requests...
                </span>
              </div>
            ) : filteredLeaves.length === 0 ? (
              <div className="py-8">
                <EmptyState
                  icon={Calendar}
                  title="No team leave requests found"
                  description={
                    leaveStatusFilter === 'PENDING'
                      ? "There are currently no pending leave requests from your direct reports requiring review."
                      : "No team leave requests match your selected status filter criteria."
                  }
                  action={
                    leaveStatusFilter !== 'ALL' ? (
                      <Button variant="secondary" size="sm" onClick={() => setLeaveStatusFilter('ALL')}>
                        Show All Team Leave Requests
                      </Button>
                    ) : null
                  }
                />
              </div>
            ) : (
              <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-xl overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-[var(--surface-2)] text-[11px] font-medium text-[var(--text-secondary)] uppercase tracking-wider border-b border-[var(--border)]">
                        <th className="py-3 px-4">Employee</th>
                        <th className="py-3 px-4">Date Range</th>
                        <th className="py-3 px-4">Reason</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Submitted On</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)] text-xs">
                      {filteredLeaves.map((leave) => {
                        const employee = reportMap[leave.employee_id];
                        const statusInfo = LEAVE_STATUS_MAP[leave.status] || { variant: 'slate', label: leave.status };
                        const duration = calculateDurationDays(leave.start_date, leave.end_date);
                        const submittedAt = new Date(leave.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        });

                        return (
                          <tr
                            key={leave.id}
                            className="hover:bg-[var(--surface-2)]/60 transition-colors"
                          >
                            <td className="py-3 px-4 whitespace-nowrap">
                              {employee ? (
                                <div className="flex flex-col">
                                  <span className="font-medium text-[var(--text-primary)]">
                                    {employee.full_name}
                                  </span>
                                  <span className="text-[10px] text-[var(--text-muted)] font-mono">
                                    {employee.employee_code || employee.email}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-[var(--text-muted)] italic">
                                  Employee #{leave.employee_id}
                                </span>
                              )}
                            </td>

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

                            <td className="py-3 px-4 max-w-xs sm:max-w-md">
                              <div className="text-[var(--text-secondary)] leading-relaxed">
                                {leave.reason}
                              </div>
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              <Badge variant={statusInfo.variant} size="sm">
                                {statusInfo.label}
                              </Badge>
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap text-right text-[var(--text-muted)]">
                              {submittedAt}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Team Performance Analytics */}
        {activeTab === 'performance' && (
          <div className="space-y-4">
            {perfError && <Alert variant="danger">{perfError}</Alert>}

            <Card className="space-y-6 p-6">
              <CardHeader className="mb-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 w-full">
                  <div>
                    <CardTitle className="text-base font-semibold">
                      {selectedEmployee
                        ? `Individual Performance: ${selectedEmployee.full_name}`
                        : 'Team Performance Aggregate'}
                    </CardTitle>
                    <CardDescription>
                      {selectedEmployee
                        ? `Analytics for employee code ${selectedEmployee.employee_code || selectedEmployee.email}`
                        : 'Combined performance metrics across all direct reports'}
                    </CardDescription>
                  </div>

                  {selectedEmployee && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setSelectedEmployee(null)}
                      className="text-xs self-start sm:self-auto"
                    >
                      <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Team Aggregate
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-8">
                {isPerfLoading ? (
                  <div className="py-16 flex flex-col items-center justify-center space-y-3">
                    <Spinner size="lg" />
                    <span className="text-xs text-[var(--text-muted)] animate-pulse">
                      Loading performance metrics...
                    </span>
                  </div>
                ) : perfStats ? (
                  <>
                    <PerformanceRing stats={perfStats} />
                    <MilestoneTrail trail={perfStats.milestone_trail} />
                  </>
                ) : null}
              </CardContent>
            </Card>
          </div>
        )}
      </main>

      {/* Task Form Modal (Scoped to direct reports only) */}
      <TaskFormModal
        isOpen={isTaskFormModalOpen}
        onClose={() => setIsTaskFormModalOpen(false)}
        onSuccess={fetchData}
        editingTask={editingTask}
        assignableEmployees={reports}
      />

      {/* Task Delete Confirmation Modal */}
      <TaskDeleteModal
        isOpen={isTaskDeleteModalOpen}
        onClose={() => setIsTaskDeleteModalOpen(false)}
        onSuccess={handleTaskDeleted}
        task={deletingTask}
      />

    </div>
  );
}

export default MyTeamPage;
