import React, { useState, useEffect } from 'react';
import { Clock, AlertTriangle } from 'lucide-react';

export function DueCountdown({ dueDatetime, status, className = '' }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    // Tick client-side once per minute (60,000 ms)
    const interval = setInterval(() => {
      setNow(new Date());
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  if (status === 'COMPLETED') {
    return (
      <span className={`inline-flex items-center gap-1 text-[11px] font-medium text-[var(--emerald)] ${className}`}>
        <Clock className="w-3 h-3" />
        <span>Completed</span>
      </span>
    );
  }

  if (!dueDatetime) {
    return <span className="text-[11px] text-[var(--text-muted)] italic">No due date</span>;
  }

  const due = new Date(dueDatetime);
  if (isNaN(due.getTime())) {
    return <span className="text-[11px] text-[var(--text-muted)] italic">Invalid date</span>;
  }

  const diffMs = due.getTime() - now.getTime();
  const isOverdue = diffMs < 0;

  let text = '';
  let colorClass = '';

  if (isOverdue) {
    const overdueMs = Math.abs(diffMs);
    const totalHours = overdueMs / (1000 * 60 * 60);
    const days = Math.floor(totalHours / 24);
    const hours = Math.floor(totalHours % 24);
    const minutes = Math.floor((overdueMs / (1000 * 60)) % 60);

    if (days > 0) {
      text = `Overdue by ${days}d ${hours}h`;
    } else if (hours > 0) {
      text = `Overdue by ${hours}h ${minutes}m`;
    } else {
      text = `Overdue by ${Math.max(1, minutes)}m`;
    }
    colorClass = 'text-[var(--red)] font-semibold';
  } else {
    const totalHours = diffMs / (1000 * 60 * 60);
    const days = Math.floor(totalHours / 24);
    const hours = Math.floor(totalHours % 24);
    const minutes = Math.floor((diffMs / (1000 * 60)) % 60);

    if (days > 0) {
      text = `${days}d ${hours}h left`;
    } else if (hours > 0) {
      text = `${hours}h ${minutes}m left`;
    } else {
      text = `${Math.max(1, minutes)}m left`;
    }

    if (totalHours > 24) {
      colorClass = 'text-[var(--text-secondary)] font-medium';
    } else if (totalHours > 2) {
      colorClass = 'text-[var(--amber)] font-medium';
    } else {
      colorClass = 'text-[var(--coral)] font-semibold';
    }
  }

  return (
    <span className={`inline-flex items-center gap-1 text-[11px] ${colorClass} ${className}`}>
      {isOverdue ? <AlertTriangle className="w-3 h-3 text-[var(--red)] shrink-0" /> : <Clock className="w-3 h-3 shrink-0" />}
      <span>{text}</span>
    </span>
  );
}

export default DueCountdown;
