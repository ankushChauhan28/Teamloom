import React from 'react';
import { CheckCircle2, Clock, AlertTriangle, Hourglass } from 'lucide-react';

export function PerformanceRing({ stats }) {
  const {
    completion_rate = 0,
    on_time_count = 0,
    late_count = 0,
    overdue_count = 0,
    pending_count = 0,
  } = stats || {};

  const totalCompleted = on_time_count + late_count;
  const percentage = Math.round((completion_rate || 0) * 100);

  // SVG ring dimensions
  const radius = 48;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius; // ~301.59
  const strokeDashoffset = circumference * (1 - (completion_rate || 0));

  return (
    <div className="flex flex-col md:flex-row items-center justify-between gap-6 p-2">
      {/* Static SVG Circular Progress Ring */}
      <div className="relative flex flex-col items-center justify-center shrink-0">
        <svg width="140" height="140" className="transform -rotate-90">
          {/* Background Track */}
          <circle
            cx="70"
            cy="70"
            r={radius}
            stroke="var(--border)"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {/* Progress Ring */}
          <circle
            cx="70"
            cy="70"
            r={radius}
            stroke="var(--teal)"
            strokeWidth={strokeWidth}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </svg>

        {/* Center Percentage Display */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-bold text-[var(--text-primary)] font-mono tracking-tight">
            {percentage}%
          </span>
          <span className="text-[10px] text-[var(--text-secondary)] font-medium uppercase tracking-wider">
            On-Time Rate
          </span>
        </div>
      </div>

      {/* Metrics Grid Breakdown */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full flex-1">
        {/* On-Time */}
        <div className="bg-[var(--surface-2)]/60 border border-[var(--border)] rounded-lg p-3 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)] mb-1">
            <span className="flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#3FA88F]" />
              <span>On-Time</span>
            </span>
          </div>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-lg font-bold font-mono text-[#3FA88F]">
              {on_time_count}
            </span>
            <span className="text-[10px] text-[var(--text-muted)] font-mono">
              of {totalCompleted} done
            </span>
          </div>
        </div>

        {/* Late */}
        <div className="bg-[var(--surface-2)]/60 border border-[var(--border)] rounded-lg p-3 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)] mb-1">
            <span className="flex items-center gap-1 font-medium">
              <Clock className="w-3.5 h-3.5 text-[#D98C6B]" />
              <span>Late</span>
            </span>
          </div>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-lg font-bold font-mono text-[#D98C6B]">
              {late_count}
            </span>
            <span className="text-[10px] text-[var(--text-muted)] font-mono">
              completed
            </span>
          </div>
        </div>

        {/* Overdue */}
        <div className="bg-[var(--surface-2)]/60 border border-[var(--border)] rounded-lg p-3 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)] mb-1">
            <span className="flex items-center gap-1 font-medium">
              <AlertTriangle className="w-3.5 h-3.5 text-[#D9695A]" />
              <span>Overdue</span>
            </span>
          </div>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-lg font-bold font-mono text-[#D9695A]">
              {overdue_count}
            </span>
            <span className="text-[10px] text-[var(--text-muted)] font-mono">
              incomplete
            </span>
          </div>
        </div>

        {/* Pending */}
        <div className="bg-[var(--surface-2)]/60 border border-[var(--border)] rounded-lg p-3 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)] mb-1">
            <span className="flex items-center gap-1 font-medium">
              <Hourglass className="w-3.5 h-3.5 text-[#D9A441]" />
              <span>Pending</span>
            </span>
          </div>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-lg font-bold font-mono text-[#D9A441]">
              {pending_count}
            </span>
            <span className="text-[10px] text-[var(--text-muted)] font-mono">
              in-progress
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PerformanceRing;
