/**
 * Utility functions for formatting dates and calculating relative due dates.
 */

export function getRelativeDueDateInfo(dueDateStr) {
  if (!dueDateStr) return { label: '', isOverdue: false };

  // Parse YYYY-MM-DD string at local midnight
  const [year, month, day] = dueDateStr.split('-').map(Number);
  const due = new Date(year, month - 1, day);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const diffMs = due.getTime() - today.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return { label: 'Due today', isOverdue: false };
  } else if (diffDays === 1) {
    return { label: 'Due tomorrow', isOverdue: false };
  } else if (diffDays > 1) {
    return { label: `Due in ${diffDays} days`, isOverdue: false };
  } else if (diffDays === -1) {
    return { label: 'Overdue by 1 day', isOverdue: true };
  } else {
    return { label: `Overdue by ${Math.abs(diffDays)} days`, isOverdue: true };
  }
}
