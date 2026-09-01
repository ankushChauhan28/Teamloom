import React from 'react';

const STATE_CONFIG = {
  on_time: {
    label: 'On-Time Completed',
    className: 'bg-[#3FA88F] border border-[#3FA88F]',
  },
  late: {
    label: 'Late Completed',
    className: 'bg-[#D98C6B] border border-[#D98C6B]',
  },
  pending: {
    label: 'Pending / In-Progress',
    className: 'bg-transparent border-2 border-[var(--text-secondary)]',
  },
  overdue: {
    label: 'Overdue & Incomplete',
    className: 'bg-transparent border-2 border-[#D9695A]',
  },
};

export function MilestoneTrail({ trail = [] }) {
  if (!trail || trail.length === 0) {
    return (
      <div className="text-xs text-[var(--text-muted)] italic py-2">
        No task milestones recorded yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
          Milestone Trail (Recent {trail.length} Tasks)
        </h4>
      </div>

      {/* Row of Task State Dots */}
      <div className="flex items-center flex-wrap gap-2.5 bg-[var(--surface-2)]/40 border border-[var(--border)] rounded-xl p-4">
        {trail.map((item) => {
          const config = STATE_CONFIG[item.state] || STATE_CONFIG.pending;
          const dueDateStr = item.due_datetime
            ? new Date(item.due_datetime).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No due date';

          const tooltipText = `${item.title} — ${config.label} (Due: ${dueDateStr})`;

          return (
            <div
              key={item.id}
              title={tooltipText}
              className={`w-4 h-4 rounded-full transition-transform hover:scale-125 cursor-help ${config.className}`}
            />
          );
        })}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-[var(--border)] text-[11px] text-[var(--text-secondary)]">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-[#3FA88F] inline-block shrink-0" />
          <span>On-Time Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-[#D98C6B] inline-block shrink-0" />
          <span>Late Completed</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full border-2 border-[var(--text-secondary)] bg-transparent inline-block shrink-0" />
          <span>Pending / In-Progress</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full border-2 border-[#D9695A] bg-transparent inline-block shrink-0" />
          <span>Overdue & Incomplete</span>
        </div>
      </div>
    </div>
  );
}

export default MilestoneTrail;
