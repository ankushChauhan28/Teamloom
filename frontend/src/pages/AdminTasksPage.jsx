import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../lib/api';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert } from '../components/ui/Alert';
import { TaskFormModal } from '../components/TaskFormModal';
import { TaskDeleteModal } from '../components/TaskDeleteModal';
import { DueCountdown } from '../components/ui/DueCountdown';
import { Plus, Edit3, Trash2, CheckSquare, RefreshCw, Filter } from 'lucide-react';


// Priority Enum -> Badge Variant & Label mapping
const PRIORITY_MAP = {
  LOW: { variant: 'slate', label: 'Low' },
  MEDIUM: { variant: 'amber', label: 'Medium' },
  HIGH: { variant: 'coral', label: 'High' },
};

// Status Enum -> Badge Variant & Label mapping
const STATUS_MAP = {
  PENDING: { variant: 'amber', label: 'Pending' },
  IN_PROGRESS: { variant: 'teal', label: 'In Progress' },
  COMPLETED: { variant: 'emerald', label: 'Completed' },
};

export function AdminTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Filter States
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [employeeFilter, setEmployeeFilter] = useState('ALL');

  // Modal States
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingTask, setDeletingTask] = useState(null);

  // Fetch all tasks system-wide & employee user list
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [tasksRes, usersRes] = await Promise.all([
        api.get('/tasks/?limit=100'),
        api.get('/users/'),
      ]);
      setTasks(tasksRes.data);
      setEmployees(usersRes.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load system tasks. Please try again.';
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

  // Filtered Task List
  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (statusFilter !== 'ALL' && task.status !== statusFilter) return false;
      if (priorityFilter !== 'ALL' && task.priority !== priorityFilter) return false;
      if (employeeFilter !== 'ALL' && String(task.assigned_to) !== employeeFilter) return false;
      return true;
    });
  }, [tasks, statusFilter, priorityFilter, employeeFilter]);

  const handleOpenCreateModal = () => {
    setEditingTask(null);
    setIsFormModalOpen(true);
  };

  const handleOpenEditModal = (task) => {
    setEditingTask(task);
    setIsFormModalOpen(true);
  };

  const handleOpenDeleteModal = (task) => {
    setDeletingTask(task);
    setIsDeleteModalOpen(true);
  };

  const handleTaskDeleted = (deletedTaskId) => {
    setTasks((prev) => prev.filter((t) => t.id !== deletedTaskId));
  };

  const employeeOptions = employees.map((emp) => ({
    value: String(emp.id),
    label: emp.full_name,
  }));

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Top Navbar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
          <div>
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">
              Task Control Panel
            </h1>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              System-wide admin management for assigning, updating, and removing employee tasks
            </p>
          </div>

          <Button variant="primary" size="md" onClick={handleOpenCreateModal} className="self-start sm:self-auto">
            <Plus className="w-4 h-4 mr-1.5" /> New Task
          </Button>
        </div>

        {/* Filter Bar */}
        <div className="bg-[var(--surface-1)] p-4 rounded-xl border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium mr-1">
              <Filter className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span>Filters:</span>
            </div>

            {/* Status Filter */}
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="py-1 px-2.5 text-xs h-8 min-w-[130px]"
              options={[
                { value: 'ALL', label: 'All Statuses' },
                { value: 'PENDING', label: 'Pending' },
                { value: 'IN_PROGRESS', label: 'In Progress' },
                { value: 'COMPLETED', label: 'Completed' },
              ]}
            />

            {/* Priority Filter */}
            <Select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="py-1 px-2.5 text-xs h-8 min-w-[130px]"
              options={[
                { value: 'ALL', label: 'All Priorities' },
                { value: 'LOW', label: 'Low' },
                { value: 'MEDIUM', label: 'Medium' },
                { value: 'HIGH', label: 'High' },
              ]}
            />

            {/* Employee Filter */}
            <Select
              value={employeeFilter}
              onChange={(e) => setEmployeeFilter(e.target.value)}
              className="py-1 px-2.5 text-xs h-8 min-w-[160px]"
              options={[
                { value: 'ALL', label: 'All Employees' },
                ...employeeOptions,
              ]}
            />
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-[var(--text-muted)] font-medium">
              Showing {filteredTasks.length} of {tasks.length} tasks
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
              Loading system tasks...
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
        ) : filteredTasks.length === 0 ? (
          <div className="py-8">
            <EmptyState
              icon={CheckSquare}
              title="No tasks found"
              description={
                tasks.length === 0
                  ? "No tasks have been created in the system yet. Click 'New Task' above to assign the first one."
                  : "No system tasks match your selected status, priority, or employee filter criteria."
              }
              action={
                tasks.length === 0 ? null : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setStatusFilter('ALL');
                      setPriorityFilter('ALL');
                      setEmployeeFilter('ALL');
                    }}
                  >
                    Reset Filters
                  </Button>
                )
              }
            />
          </div>
        ) : (
          /* System-Wide Task Table */
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
                    const assignee = employeeMap[task.assigned_to];
                    const priorityInfo = PRIORITY_MAP[task.priority] || { variant: 'slate', label: task.priority };
                    const statusInfo = STATUS_MAP[task.status] || { variant: 'slate', label: task.status };

                    return (
                      <tr
                        key={task.id}
                        className="hover:bg-[var(--surface-2)]/60 transition-colors"
                      >
                        {/* Title & Short Description */}
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

                        {/* Assigned Employee */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {assignee ? (
                            <div className="flex flex-col">
                              <span className="font-medium text-[var(--text-primary)]">
                                {assignee.full_name}
                              </span>
                              <span className="text-[10px] text-[var(--text-muted)] font-mono">
                                {assignee.email}
                              </span>
                            </div>
                          ) : (
                            <span className="text-[var(--text-muted)] italic">
                              User #{task.assigned_to}
                            </span>
                          )}
                        </td>

                        {/* Priority Badge */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <Badge variant={priorityInfo.variant} size="sm">
                            {priorityInfo.label}
                          </Badge>
                        </td>

                        {/* Status Badge */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <Badge variant={statusInfo.variant} size="sm">
                            {statusInfo.label}
                          </Badge>
                        </td>

                        {/* Due Date & Time Countdown */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <DueCountdown dueDatetime={task.due_datetime || task.due_date} status={task.status} />
                        </td>

                        {/* Actions (Edit / Delete) */}
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenEditModal(task)}
                              className="p-1.5 h-8 text-[var(--text-secondary)] hover:text-[var(--accent)]"
                              title="Edit Task"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenDeleteModal(task)}
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
      </main>

      {/* Task Form Modal (Create & Edit) */}
      <TaskFormModal
        isOpen={isFormModalOpen}
        onClose={() => setIsFormModalOpen(false)}
        onSuccess={fetchData}
        editingTask={editingTask}
      />

      {/* Task Delete Confirmation Modal */}
      <TaskDeleteModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onSuccess={handleTaskDeleted}
        task={deletingTask}
      />
    </div>
  );
}

export default AdminTasksPage;
