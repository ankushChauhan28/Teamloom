import React, { useState, useEffect, useCallback } from 'react';
import { CheckSquare, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { TaskCard } from './TaskCard';
import { Spinner } from './ui/Spinner';
import { EmptyState } from './ui/EmptyState';
import { Alert } from './ui/Alert';
import { Button } from './ui/Button';

export function TaskList() {
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchTasks = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      // Fetch assigned tasks (limit 50 to avoid default pagination truncation)
      const res = await api.get('/tasks/?limit=50');
      setTasks(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load assigned tasks. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleStatusChange = async (taskId, newStatus) => {
    const currentTask = tasks.find((t) => t.id === taskId);
    try {
      // 1. Call API to update task status with current version
      const res = await api.patch(`/tasks/${taskId}`, {
        status: newStatus,
        version: currentTask?.version,
      });
      const updatedTask = res.data;

      // 2. Update task in local state on success
      setTasks((prevTasks) =>
        prevTasks.map((t) => (t.id === taskId ? updatedTask : t))
      );

      return updatedTask;
    } catch (err) {
      if (err.response?.status === 409) {
        setError('This task was updated elsewhere. Refreshing your task list...');
        await fetchTasks();
      }
      throw err;
    }
  };

  if (isLoading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center space-y-3">
        <Spinner size="lg" />
        <span className="text-xs text-[var(--text-muted)] animate-pulse">
          Loading assigned tasks...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Alert variant="danger">{error}</Alert>
        <div className="flex justify-center">
          <Button variant="secondary" size="sm" onClick={fetchTasks}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry Loading
          </Button>
        </div>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="py-8">
        <EmptyState
          icon={CheckSquare}
          title="No tasks assigned yet"
          description="You don't have any active tasks assigned to you right now. New task assignments will appear here."
          action={
            <Button variant="secondary" size="sm" onClick={fetchTasks}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh List
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header bar with count and refresh */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium text-[var(--text-primary)]">
            My Assigned Tasks
          </h2>
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--surface-2)] text-[var(--accent)] border border-[var(--border)]">
            {tasks.length}
          </span>
        </div>

        <Button variant="ghost" size="sm" onClick={fetchTasks} className="text-xs text-[var(--text-muted)]">
          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
        </Button>
      </div>

      {/* Responsive Card Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onStatusChange={handleStatusChange}
          />
        ))}
      </div>
    </div>
  );
}

export default TaskList;
