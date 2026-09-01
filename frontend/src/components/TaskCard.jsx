import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Card } from './ui/Card';
import { Badge } from './ui/Badge';
import { Select } from './ui/Select';
import { Spinner } from './ui/Spinner';
import { DueCountdown } from './ui/DueCountdown';

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

export function TaskCard({ task, onStatusChange }) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState('');

  const priorityInfo = PRIORITY_MAP[task.priority] || { variant: 'slate', label: task.priority };
  const statusInfo = STATUS_MAP[task.status] || { variant: 'slate', label: task.status };

  const handleStatusSelect = async (e) => {
    const newStatus = e.target.value;
    if (newStatus === task.status) return;

    setUpdateError('');
    setIsUpdating(true);
    try {
      await onStatusChange(task.id, newStatus);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to update status.';
      setUpdateError(msg);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <Card className="p-4 flex flex-col justify-between space-y-3.5 hover:border-[var(--border-strong)] transition-all">
      {/* Top Header: Title & Priority Badge */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-medium text-[var(--text-primary)] leading-snug break-words">
          {task.title}
        </h3>
        <Badge variant={priorityInfo.variant} size="sm" className="shrink-0">
          {priorityInfo.label}
        </Badge>
      </div>

      {/* Description: Truncated to 2 lines */}
      <p className="text-xs text-[var(--text-muted)] line-clamp-2 leading-relaxed">
        {task.description || 'No description provided.'}
      </p>

      {/* Due Date & Current Status Badge */}
      <div className="flex items-center justify-between text-xs pt-1 border-t border-[var(--border)]">
        {/* Live Due Countdown Component */}
        <DueCountdown dueDatetime={task.due_datetime || task.due_date} status={task.status} />

        {/* Current Status Badge */}
        <Badge variant={statusInfo.variant} size="sm">
          {statusInfo.label}
        </Badge>
      </div>

      {/* Inline Status Control */}
      <div className="pt-2 border-t border-[var(--border)] flex flex-col space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-medium text-[var(--text-secondary)] shrink-0">
            Update Status:
          </span>

          <div className="flex items-center gap-2 flex-1 justify-end">
            {isUpdating ? (
              <div className="flex items-center gap-1.5 py-1 px-2 text-xs text-[var(--accent)] font-medium">
                <Spinner size="sm" />
                <span className="text-[11px]">Updating...</span>
              </div>
            ) : (
              <Select
                value={task.status}
                onChange={handleStatusSelect}
                disabled={isUpdating}
                className="py-1 px-2 text-xs h-8 max-w-[140px]"
                options={[
                  { value: 'PENDING', label: 'Pending' },
                  { value: 'IN_PROGRESS', label: 'In Progress' },
                  { value: 'COMPLETED', label: 'Completed' },
                ]}
              />
            )}
          </div>
        </div>

        {/* Inline Error Text on Update Failure */}
        {updateError && (
          <div className="flex items-center gap-1 text-[11px] text-[var(--red)] mt-1">
            <AlertTriangle className="w-3 h-3 shrink-0" />
            <span>{updateError}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

export default TaskCard;
