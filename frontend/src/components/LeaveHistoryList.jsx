import React, { useState, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react';
import { api } from '../lib/api';
import { Card } from './ui/Card';
import { Badge } from './ui/Badge';
import { Spinner } from './ui/Spinner';
import { EmptyState } from './ui/EmptyState';
import { Alert } from './ui/Alert';
import { Button } from './ui/Button';
import { Calendar, RefreshCw, Clock } from 'lucide-react';

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

export const LeaveHistoryList = forwardRef(({ refreshTrigger }, ref) => {
  const [leaves, setLeaves] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchLeaves = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const res = await api.get('/leaves/?limit=50');
      setLeaves(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load leave history. Please try again.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLeaves();
  }, [fetchLeaves, refreshTrigger]);

  useImperativeHandle(ref, () => ({
    refresh: fetchLeaves,
  }));

  if (isLoading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center space-y-3">
        <Spinner size="lg" />
        <span className="text-xs text-[var(--text-muted)] animate-pulse">
          Loading leave history...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Alert variant="danger">{error}</Alert>
        <div className="flex justify-center">
          <Button variant="secondary" size="sm" onClick={fetchLeaves}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry Loading
          </Button>
        </div>
      </div>
    );
  }

  if (leaves.length === 0) {
    return (
      <div className="py-6">
        <EmptyState
          icon={Calendar}
          title="No leave requests submitted yet"
          description="Your personal leave request history will appear here once you submit a request above."
          action={
            <Button variant="secondary" size="sm" onClick={fetchLeaves}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh List
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* List Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-[var(--text-primary)]">
            My Leave Requests
          </h3>
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--surface-2)] text-[var(--accent)] border border-[var(--border)]">
            {leaves.length}
          </span>
        </div>

        <Button variant="ghost" size="sm" onClick={fetchLeaves} className="text-xs text-[var(--text-muted)]">
          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
        </Button>
      </div>

      {/* Stacked Cards List */}
      <div className="space-y-3">
        {leaves.map((leave) => {
          const statusInfo = STATUS_MAP[leave.status] || { variant: 'slate', label: leave.status };
          const duration = calculateDurationDays(leave.start_date, leave.end_date);
          const submittedAt = new Date(leave.created_at).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          });

          return (
            <Card key={leave.id} className="p-4 space-y-2.5 hover:border-[var(--border-strong)] transition-all">
              {/* Header: Dates & Status Badge */}
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {leave.start_date} <span className="text-[var(--text-muted)] mx-1">→</span> {leave.end_date}
                  </span>
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-[var(--surface-2)] text-[var(--text-secondary)] border border-[var(--border)]">
                    {duration} {duration === 1 ? 'day' : 'days'}
                  </span>
                </div>

                <Badge variant={statusInfo.variant} size="sm">
                  {statusInfo.label}
                </Badge>
              </div>

              {/* Reason Description */}
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                {leave.reason}
              </p>

              {/* Footer: Submitted timestamp */}
              <div className="flex items-center gap-1 text-[11px] text-[var(--text-muted)] pt-1 border-t border-[var(--border)]">
                <Clock className="w-3 h-3" />
                <span>Submitted on {submittedAt}</span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
});

LeaveHistoryList.displayName = 'LeaveHistoryList';
export default LeaveHistoryList;
