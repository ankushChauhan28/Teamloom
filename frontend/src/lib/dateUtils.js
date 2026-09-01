/**
 * Utility functions for formatting dates, ISO datetimes, and datetime-local inputs.
 */

/**
 * Format a Date object or ISO string into `YYYY-MM-DDTHH:mm` format
 * for HTML5 `<input type="datetime-local">`.
 */
export function formatToDatetimeLocal(dateOrIsoStr) {
  if (!dateOrIsoStr) return '';
  const date = new Date(dateOrIsoStr);
  if (isNaN(date.getTime())) return '';

  const pad = (num) => String(num).padStart(2, '0');
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());

  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * Format ISO datetime string into human-readable local date & time.
 * e.g. "Aug 24, 2026, 6:30 PM"
 */
export function formatDisplayDatetime(dateOrIsoStr) {
  if (!dateOrIsoStr) return '';
  const date = new Date(dateOrIsoStr);
  if (isNaN(date.getTime())) return '';

  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Legacy relative due date helper fallback.
 */
export function getRelativeDueDateInfo(dueDateStr) {
  if (!dueDateStr) return { label: '', isOverdue: false };

  const due = new Date(dueDateStr);
  if (isNaN(due.getTime())) return { label: '', isOverdue: false };

  const now = new Date();
  const diffMs = due.getTime() - now.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffMs < 0) {
    const overdueHours = Math.abs(diffHours);
    if (overdueHours < 24) {
      return { label: `Overdue by ${Math.ceil(overdueHours)}h`, isOverdue: true };
    }
    const days = Math.floor(overdueHours / 24);
    return { label: `Overdue by ${days}d`, isOverdue: true };
  } else {
    if (diffHours < 24) {
      return { label: `Due in ${Math.ceil(diffHours)}h`, isOverdue: false };
    }
    const days = Math.floor(diffHours / 24);
    return { label: `Due in ${days}d`, isOverdue: false };
  }
}
